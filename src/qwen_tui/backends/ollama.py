"""
Ollama backend implementation for Qwen-TUI.

Provides integration with Ollama local inference server with automatic
model discovery and streaming support.
"""
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import time

from .base import LLMBackend, LLMRequest, LLMResponse, BackendStatus, BackendInfo
from ..exceptions import BackendError, BackendConnectionError, BackendTimeoutError
from ..config import OllamaConfig


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLM inference."""
    
    def __init__(self, config: OllamaConfig, name: str = "ollama"):
        super().__init__(config.dict(), name)
        self.ollama_config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self.session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[str] = []
        self._model_cache_time = 0
        self._model_cache_ttl = 300  # 5 minutes
        
    @property
    def backend_type(self) -> str:
        return "ollama"
    
    async def initialize(self) -> None:
        """Initialize the Ollama backend."""
        self.logger.info("Initializing Ollama backend", 
                        host=self.ollama_config.host,
                        port=self.ollama_config.port)
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=self._connection_timeout)
        # Allow ClientSession to pick up proxy settings from the environment.
        self.session = aiohttp.ClientSession(timeout=timeout, trust_env=True)
        
        # Test connection
        try:
            await self.health_check()
            self._status = BackendStatus.CONNECTED
            self.logger.info("Ollama backend initialized successfully")
        except Exception as e:
            if self.session:
                await self.session.close()
                self.session = None
            self._status = BackendStatus.ERROR
            self.logger.error(
                "Failed to initialize Ollama backend", error=str(e)
            )
            raise BackendConnectionError(
                f"Failed to connect to Ollama at {self.base_url}",
                backend_name=self.name,
                cause=e
            )
    
    async def cleanup(self) -> None:
        """Clean up Ollama backend resources."""
        if self.session:
            await self.session.close()
            self.session = None
        self._status = BackendStatus.DISCONNECTED
        self.logger.info("Ollama backend cleaned up")
    
    async def health_check(self) -> bool:
        """Check if Ollama is healthy and responsive."""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.base_url}/api/version") as response:
                if response.status == 200:
                    self._status = BackendStatus.AVAILABLE
                    return True
                else:
                    self._status = BackendStatus.UNAVAILABLE
                    return False
        except Exception as e:
            self.logger.debug("Ollama health check failed", error=str(e))
            self._status = BackendStatus.ERROR
            return False
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models from Ollama."""
        current_time = time.time()
        
        # Return cached models if still valid
        if (current_time - self._model_cache_time) < self._model_cache_ttl and self._available_models:
            return self._available_models
        
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    self._available_models = models
                    self._model_cache_time = current_time
                    return models
                else:
                    raise BackendError(
                        f"Failed to get models: HTTP {response.status}",
                        backend_name=self.name
                    )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to Ollama: {str(e)}",
                backend_name=self.name,
                cause=e
            )
    
    async def get_info(self) -> BackendInfo:
        """Get detailed backend information."""
        info = await super().get_info()
        
        try:
            # Get version info
            if self.session:
                async with self.session.get(f"{self.base_url}/api/version") as response:
                    if response.status == 200:
                        version_data = await response.json()
                        info.version = version_data.get("version", "unknown")
            
            # Get available models
            models = await self.get_available_models()
            info.capabilities = [f"models: {len(models)}"] + models[:5]  # Show first 5 models
            
        except Exception as e:
            info.error_message = str(e)
        
        return info
    
    async def generate(self, request: LLMRequest) -> AsyncGenerator[LLMResponse, None]:
        """Generate response using Ollama."""
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        # Prepare request
        request = self._prepare_request(request)
        
        # Convert request to Ollama format
        ollama_request = self._convert_to_ollama_request(request)
        
        self.logger.info("Sending request to Ollama",
                        model=request.model,
                        messages=len(request.messages),
                        tools=len(request.tools) if request.tools else 0)

        self.logger.debug("Ollama request payload", payload=ollama_request)
        
        start_time = time.time()
        
        try:
            # Use appropriate endpoint based on whether tools are present
            endpoint = "/api/chat"
            
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=ollama_request,
                timeout=aiohttp.ClientTimeout(total=self._request_timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    
                    # Parse error for better messages
                    error_message = f"Ollama request failed: HTTP {response.status} - {error_text}"
                    
                    # Provide helpful messages for common errors
                    if response.status == 404 and "not found" in error_text:
                        model_name = request.model or self.ollama_config.model
                        available_models = []
                        try:
                            available_models = await self.get_available_models()
                        except:
                            pass
                        
                        error_message = f"Model '{model_name}' not found in Ollama. "
                        if available_models:
                            error_message += f"Available models: {', '.join(available_models[:3])}"
                            if len(available_models) > 3:
                                error_message += f" (and {len(available_models) - 3} more)"
                        else:
                            error_message += f"Try running 'ollama pull {model_name}' first."
                    
                    raise BackendError(error_message, backend_name=self.name)
                
                if request.stream:
                    # Handle streaming response
                    async for chunk in self._handle_streaming_response(response, start_time):
                        yield chunk
                else:
                    # Handle non-streaming response
                    data = await response.json()
                    yield self._convert_from_ollama_response(data, start_time)
                    
        except asyncio.TimeoutError:
            raise BackendTimeoutError(
                f"Ollama request timed out after {self._request_timeout}s",
                backend_name=self.name
            )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to Ollama: {str(e)}",
                backend_name=self.name,
                cause=e
            )
    
    def _convert_to_ollama_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Convert LLMRequest to Ollama API format."""
        ollama_request = {
            "model": request.model or self.ollama_config.model,
            "messages": request.messages,
            "stream": request.stream,
            "options": {}
        }
        
        # Add generation parameters
        if request.temperature is not None:
            ollama_request["options"]["temperature"] = request.temperature
        
        if request.max_tokens is not None:
            ollama_request["options"]["num_predict"] = request.max_tokens
        
        if request.top_p is not None:
            ollama_request["options"]["top_p"] = request.top_p
        
        # Add tools if present
        if request.tools:
            ollama_request["tools"] = request.tools
        
        # Add backend-specific parameters
        if request.backend_params:
            ollama_request["options"].update(request.backend_params)
        
        # Add keep_alive setting
        if hasattr(self.ollama_config, 'keep_alive'):
            ollama_request["keep_alive"] = self.ollama_config.keep_alive
        
        return ollama_request
    
    def _convert_from_ollama_response(self, data: Dict[str, Any], start_time: float) -> LLMResponse:
        """Convert Ollama response to LLMResponse format."""
        message = data.get("message", {})
        
        # Extract tool calls if present
        tool_calls = None
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
        
        # Extract usage information
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            }
        
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=data.get("done_reason", "stop" if data.get("done", False) else None),
            model=data.get("model"),
            response_time=time.time() - start_time,
            backend_metadata={
                "backend": self.name,
                "load_duration": data.get("load_duration"),
                "prompt_eval_duration": data.get("prompt_eval_duration"),
                "eval_duration": data.get("eval_duration"),
                "total_duration": data.get("total_duration")
            }
        )
    
    async def _handle_streaming_response(
        self, 
        response: aiohttp.ClientResponse, 
        start_time: float
    ) -> AsyncGenerator[LLMResponse, None]:
        """Handle streaming response from Ollama."""
        buffer = ""

        async for chunk in response.content.iter_any():
            self.logger.debug("Received stream chunk", size=len(chunk))
            buffer += chunk.decode('utf-8', errors='ignore')
            
            # Process complete JSON lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Convert to standard response format
                    ollama_response = self._convert_from_ollama_response(data, start_time)
                    
                    # Mark as partial if not done
                    if not data.get("done", False):
                        ollama_response.is_partial = True
                        ollama_response.delta = data.get("message", {}).get("content", "")
                        self.logger.debug("Streaming delta", delta=ollama_response.delta)
                    
                    yield ollama_response
                    
                    # Break if this is the final chunk
                    if data.get("done", False):
                        break
                        
                except json.JSONDecodeError as e:
                    self.logger.warning("Failed to parse streaming response chunk",
                                      chunk=line,
                                      error=str(e))
                    continue
    
    async def pull_model(self, model_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Pull a model from Ollama registry."""
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        self.logger.info("Pulling model from Ollama", model=model_name)
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True}
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise BackendError(
                        f"Failed to pull model {model_name}: HTTP {response.status} - {error_text}",
                        backend_name=self.name
                    )
                
                buffer = ""
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode('utf-8', errors='ignore')
                    
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            yield data
                            
                            if data.get("status") == "success":
                                # Clear model cache to refresh available models
                                self._model_cache_time = 0
                                break
                                
                        except json.JSONDecodeError:
                            continue
                            
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to Ollama: {str(e)}",
                backend_name=self.name,
                cause=e
            )
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        self.logger.info("Deleting model from Ollama", model=model_name)
        
        try:
            async with self.session.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name}
            ) as response:
                
                if response.status == 200:
                    # Clear model cache to refresh available models
                    self._model_cache_time = 0
                    return True
                else:
                    return False
                    
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to Ollama: {str(e)}",
                backend_name=self.name,
                cause=e
            )