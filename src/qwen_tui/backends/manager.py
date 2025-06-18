"""
Backend manager for Qwen-TUI.

Handles backend discovery, health monitoring, failover, and request routing
across multiple LLM backends.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Type, Union, AsyncGenerator
from enum import Enum

from .base import LLMBackend, LLMRequest, LLMResponse, BackendStatus, BackendPool
from .ollama import OllamaBackend
from .lm_studio import LMStudioBackend
from ..config import Config, BackendType
from ..exceptions import BackendError, BackendUnavailableError
from ..logging import get_main_logger


class BackendManager:
    """
    Manages multiple LLM backends with automatic discovery, health monitoring,
    and intelligent request routing.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_main_logger()
        self.backends: Dict[BackendType, LLMBackend] = {}
        self.backend_pool: Optional[BackendPool] = None
        self._last_discovery = 0
        self._discovery_interval = 60  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize the backend manager and discover backends."""
        self.logger.info("Initializing backend manager")
        
        # Discover and initialize backends
        await self.discover_backends()
        
        # Start periodic health checks
        self._health_check_task = asyncio.create_task(self._periodic_health_checks())
        
        self.logger.info("Backend manager initialized",
                        backends=list(self.backends.keys()))
    
    async def cleanup(self) -> None:
        """Clean up all backends and tasks."""
        self.logger.info("Cleaning up backend manager")
        
        # Stop health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Clean up all backends
        if self.backend_pool:
            await self.backend_pool.cleanup_all()
        
        self.backends.clear()
        self.backend_pool = None
        
        self.logger.info("Backend manager cleaned up")
    
    async def discover_backends(self) -> Dict[BackendType, Dict[str, Any]]:
        """
        Discover and initialize available backends.
        
        Returns:
            Dictionary mapping backend types to their discovery results
        """
        self.logger.info("Discovering available backends")
        results = {}
        
        # Backend factory mapping
        backend_factories = {
            BackendType.OLLAMA: self._create_ollama_backend,
            BackendType.LM_STUDIO: self._create_lm_studio_backend,
            BackendType.VLLM: self._create_vllm_backend,
            BackendType.OPENROUTER: self._create_openrouter_backend
        }
        
        # Try to initialize each backend type
        for backend_type in BackendType:
            try:
                self.logger.info(f"Discovering {backend_type.value} backend")
                
                factory = backend_factories.get(backend_type)
                if not factory:
                    results[backend_type] = {
                        "available": False,
                        "error": f"No factory for {backend_type.value}"
                    }
                    continue
                
                backend = await factory()
                if backend:
                    # Test the backend
                    test_result = await backend.test_connection()
                    
                    if test_result["success"]:
                        self.backends[backend_type] = backend
                        results[backend_type] = {
                            "available": True,
                            "backend": backend,
                            "host": backend.config.get("host"),
                            "port": backend.config.get("port"),
                            "model": backend.config.get("model"),
                            "response_time": test_result.get("response_time"),
                            "notes": "Ready to use"
                        }
                        self.logger.info(f"{backend_type.value} backend discovered and ready")
                    else:
                        results[backend_type] = {
                            "available": False,
                            "error": test_result.get("error", "Connection test failed")
                        }
                        await backend.cleanup()
                else:
                    results[backend_type] = {
                        "available": False,
                        "error": "Backend creation failed"
                    }
                    
            except Exception as e:
                self.logger.error(f"Failed to discover {backend_type.value} backend",
                                error=str(e),
                                error_type=type(e).__name__)
                results[backend_type] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Create backend pool from available backends
        available_backends = [b for b in self.backends.values()]
        if available_backends:
            self.backend_pool = BackendPool(available_backends)
            self.logger.info(f"Created backend pool with {len(available_backends)} backends")
        else:
            self.logger.warning("No backends are available")
        
        self._last_discovery = time.time()
        return results
    
    async def _create_ollama_backend(self) -> Optional[OllamaBackend]:
        """Create and initialize Ollama backend."""
        try:
            backend = OllamaBackend(self.config.ollama)
            await backend.initialize()
            return backend
        except Exception as e:
            self.logger.debug("Ollama backend not available", error=str(e))
            return None
    
    async def _create_lm_studio_backend(self) -> Optional[LMStudioBackend]:
        """Create and initialize LM Studio backend."""
        try:
            backend = LMStudioBackend(self.config.lm_studio)
            await backend.initialize()
            return backend
        except Exception as e:
            self.logger.debug("LM Studio backend not available", error=str(e))
            return None
    
    async def _create_vllm_backend(self) -> Optional[LLMBackend]:
        """Create and initialize vLLM backend."""
        try:
            from .vllm import VLLMBackend
            backend = VLLMBackend(self.config.vllm)
            await backend.initialize()
            return backend
        except ImportError:
            self.logger.debug("vLLM backend not implemented yet")
            return None
        except Exception as e:
            self.logger.debug("vLLM backend not available", error=str(e))
            return None
    
    async def _create_openrouter_backend(self) -> Optional[LLMBackend]:
        """Create and initialize OpenRouter backend."""
        try:
            from .openrouter import OpenRouterBackend
            backend = OpenRouterBackend(self.config.openrouter)
            await backend.initialize()
            return backend
        except ImportError:
            self.logger.debug("OpenRouter backend not implemented yet")
            return None
        except Exception as e:
            self.logger.debug("OpenRouter backend not available", error=str(e))
            return None
    
    def get_backend(self, backend_type: BackendType) -> Optional[LLMBackend]:
        """Get a specific backend by type."""
        return self.backends.get(backend_type)
    
    def get_preferred_backend(self) -> Optional[LLMBackend]:
        """Get the most preferred available backend."""
        if not self.backend_pool:
            return None
        
        preferred_types = [bt.value for bt in self.config.preferred_backends]
        return self.backend_pool.get_preferred_backend(preferred_types)
    
    def get_available_backends(self) -> List[LLMBackend]:
        """Get list of all available backends."""
        if not self.backend_pool:
            return []
        return self.backend_pool.get_healthy_backends()
    
    async def generate(
        self,
        request: LLMRequest,
        preferred_backend: Optional[BackendType] = None,
        fallback: bool = True
    ) -> AsyncGenerator[LLMResponse, None]:
        """
        Generate response using available backends with fallback support.
        
        Args:
            request: The LLM request
            preferred_backend: Specific backend to try first
            fallback: Whether to try other backends if preferred fails
        """
        if not self.backend_pool:
            raise BackendUnavailableError("No backends are available")
        
        # Determine which backend to use
        if preferred_backend:
            backend = self.get_backend(preferred_backend)
            if not backend or backend.status != BackendStatus.AVAILABLE:
                if not fallback:
                    raise BackendUnavailableError(
                        f"Preferred backend {preferred_backend.value} is not available"
                    )
                backend = self.get_preferred_backend()
        else:
            backend = self.get_preferred_backend()
        
        if not backend:
            raise BackendUnavailableError("No healthy backends are available")
        
        self.logger.info("Routing request to backend",
                        backend=backend.name,
                        model=request.model,
                        messages=len(request.messages))
        
        try:
            # Try primary backend
            async for response in backend.generate(request):
                yield response
            return
            
        except Exception as e:
            self.logger.warning(f"Request failed on {backend.name}",
                              backend=backend.name,
                              error=str(e))
            
            if not fallback:
                raise
            
            # Try fallback backends
            available_backends = self.get_available_backends()
            fallback_backends = [b for b in available_backends if b != backend]
            
            for fallback_backend in fallback_backends:
                try:
                    self.logger.info(f"Trying fallback backend {fallback_backend.name}")
                    
                    async for response in fallback_backend.generate(request):
                        yield response
                    return
                    
                except Exception as fallback_error:
                    self.logger.warning(f"Fallback failed on {fallback_backend.name}",
                                      backend=fallback_backend.name,
                                      error=str(fallback_error))
                    continue
            
            # All backends failed
            raise BackendError(
                f"All backends failed. Last error: {str(e)}",
                context={"attempted_backends": [b.name for b in [backend] + fallback_backends]}
            )
    
    async def test_all_backends(self) -> Dict[BackendType, Dict[str, Any]]:
        """Test connectivity to all configured backends."""
        results = {}
        
        for backend_type, backend in self.backends.items():
            try:
                result = await backend.test_connection()
                results[backend_type] = result
            except Exception as e:
                results[backend_type] = {
                    "success": False,
                    "error": str(e),
                    "backend": backend.name
                }
        
        return results
    
    async def get_backend_info(self) -> Dict[BackendType, Dict[str, Any]]:
        """Get detailed information about all backends."""
        info = {}
        
        for backend_type, backend in self.backends.items():
            try:
                backend_info = await backend.get_info()
                info[backend_type] = {
                    "name": backend_info.name,
                    "type": backend_info.backend_type,
                    "status": backend_info.status.value,
                    "host": backend_info.host,
                    "port": backend_info.port,
                    "model": backend_info.model,
                    "version": backend_info.version,
                    "capabilities": backend_info.capabilities,
                    "last_check": backend_info.last_check,
                    "error": backend_info.error_message
                }
            except Exception as e:
                info[backend_type] = {
                    "name": backend.name,
                    "type": backend.backend_type,
                    "status": "error",
                    "error": str(e)
                }
        
        return info
    
    async def switch_backend(self, backend_type: BackendType) -> bool:
        """Switch to a specific backend as the primary choice."""
        backend = self.get_backend(backend_type)
        if not backend:
            return False
        
        # Move the backend to the front of preferences
        new_preferences = [backend_type]
        new_preferences.extend([bt for bt in self.config.preferred_backends if bt != backend_type])
        self.config.preferred_backends = new_preferences
        
        self.logger.info(f"Switched to {backend_type.value} as primary backend")
        return True
    
    async def _periodic_health_checks(self) -> None:
        """Perform periodic health checks on all backends."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self.backends:
                    self.logger.debug("Performing periodic health checks")
                    
                    # Check each backend
                    for backend_type, backend in self.backends.items():
                        try:
                            await backend.periodic_health_check()
                        except Exception as e:
                            self.logger.error(f"Health check failed for {backend_type.value}",
                                            error=str(e))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in periodic health checks", error=str(e))
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of backend status."""
        if not self.backends:
            return {
                "total_backends": 0,
                "available_backends": 0,
                "preferred_backend": None,
                "status": "no_backends"
            }
        
        available_backends = self.get_available_backends()
        preferred = self.get_preferred_backend()
        
        return {
            "total_backends": len(self.backends),
            "available_backends": len(available_backends),
            "preferred_backend": preferred.name if preferred else None,
            "backend_status": {
                bt.value: backend.status.value 
                for bt, backend in self.backends.items()
            },
            "status": "healthy" if available_backends else "unhealthy"
        }
    
    # Model Management Methods
    
    async def get_all_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available models from all backends."""
        all_models = {}
        
        for backend_type, backend in self.backends.items():
            try:
                if hasattr(backend, 'get_detailed_models'):
                    # Enhanced model info (LM Studio, etc.)
                    models = await backend.get_detailed_models()
                    all_models[backend_type.value] = [
                        {
                            "id": model.get("id", "unknown"),
                            "name": model.get("id", "unknown"),
                            "backend": backend_type.value,
                            "object": model.get("object", "model"),
                            "created": model.get("created"),
                            "owned_by": model.get("owned_by", "local"),
                            "details": model
                        }
                        for model in models
                    ]
                else:
                    # Basic model list (Ollama, etc.)
                    model_ids = await backend.get_available_models()
                    all_models[backend_type.value] = [
                        {
                            "id": model_id,
                            "name": model_id,
                            "backend": backend_type.value,
                            "object": "model",
                            "owned_by": "local"
                        }
                        for model_id in model_ids
                    ]
                    
            except Exception as e:
                self.logger.error(f"Failed to get models from {backend_type.value}",
                                error=str(e))
                all_models[backend_type.value] = []
        
        return all_models
    
    async def get_models_by_backend(self, backend_type: BackendType) -> List[Dict[str, Any]]:
        """Get models from a specific backend."""
        backend = self.get_backend(backend_type)
        if not backend:
            return []
        
        try:
            if hasattr(backend, 'get_detailed_models'):
                models = await backend.get_detailed_models()
                return [
                    {
                        "id": model.get("id", "unknown"),
                        "name": model.get("id", "unknown"),
                        "backend": backend_type.value,
                        "object": model.get("object", "model"),
                        "created": model.get("created"),
                        "owned_by": model.get("owned_by", "local"),
                        "details": model
                    }
                    for model in models
                ]
            else:
                model_ids = await backend.get_available_models()
                return [
                    {
                        "id": model_id,
                        "name": model_id,
                        "backend": backend_type.value,
                        "object": "model",
                        "owned_by": "local"
                    }
                    for model_id in model_ids
                ]
        except Exception as e:
            self.logger.error(f"Failed to get models from {backend_type.value}",
                            error=str(e))
            return []
    
    async def get_current_models(self) -> Dict[str, Optional[str]]:
        """Get currently active/loaded model for each backend."""
        current_models = {}
        
        for backend_type, backend in self.backends.items():
            try:
                if hasattr(backend, '_current_model'):
                    current_models[backend_type.value] = backend._current_model
                elif hasattr(backend, 'config') and 'model' in backend.config:
                    current_models[backend_type.value] = backend.config['model']
                else:
                    current_models[backend_type.value] = None
            except Exception as e:
                self.logger.error(f"Failed to get current model from {backend_type.value}",
                                error=str(e))
                current_models[backend_type.value] = None
        
        return current_models
    
    async def switch_model(self, backend_type: BackendType, model_id: str) -> bool:
        """Switch to a specific model on a backend."""
        backend = self.get_backend(backend_type)
        if not backend:
            self.logger.error(f"Backend {backend_type.value} not found")
            return False
        
        try:
            if hasattr(backend, 'switch_model'):
                # Backend supports direct model switching
                success = await backend.switch_model(model_id)
                if success:
                    self.logger.info(f"Successfully switched {backend_type.value} to model {model_id}")
                return success
            else:
                # Update configuration for backends that don't support runtime switching
                backend.config['model'] = model_id
                self.logger.info(f"Updated {backend_type.value} model preference to {model_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to switch model on {backend_type.value}",
                            model=model_id,
                            error=str(e))
            return False
    
    async def get_model_info(self, backend_type: BackendType, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        backend = self.get_backend(backend_type)
        if not backend:
            return None
        
        try:
            if hasattr(backend, 'get_model_info'):
                return await backend.get_model_info(model_id)
            else:
                # Fallback: check if model exists in available models
                models = await self.get_models_by_backend(backend_type)
                for model in models:
                    if model['id'] == model_id:
                        return model
                return None
        except Exception as e:
            self.logger.error(f"Failed to get model info from {backend_type.value}",
                            model=model_id,
                            error=str(e))
            return None
    
    async def is_model_available(self, backend_type: BackendType, model_id: str) -> bool:
        """Check if a specific model is available on a backend."""
        try:
            models = await self.get_models_by_backend(backend_type)
            return any(model['id'] == model_id for model in models)
        except Exception:
            return False
    
    async def find_model_across_backends(self, model_pattern: str) -> List[Dict[str, Any]]:
        """Find models matching a pattern across all backends."""
        matching_models = []
        all_models = await self.get_all_models()
        
        for backend, models in all_models.items():
            for model in models:
                if (model_pattern.lower() in model['id'].lower() or 
                    model_pattern.lower() in model['name'].lower()):
                    matching_models.append(model)
        
        return matching_models
    
    async def get_recommended_models(self) -> List[Dict[str, Any]]:
        """Get recommended models for coding tasks."""
        recommended_patterns = [
            "qwen2.5-coder",
            "qwen-coder", 
            "qwen3",
            "codeqwen",
            "starcoder",
            "codellama",
            "deepseek-coder",
            "deepcoder"
        ]
        
        recommended_models = []
        
        for pattern in recommended_patterns:
            matches = await self.find_model_across_backends(pattern)
            recommended_models.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_models = []
        for model in recommended_models:
            key = (model['backend'], model['id'])
            if key not in seen:
                seen.add(key)
                unique_models.append(model)
        
        return unique_models