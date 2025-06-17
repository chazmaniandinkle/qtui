"""
Base backend interface for Qwen-TUI.

Defines the abstract interface that all LLM backends must implement,
providing consistent API across different backend types.
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from ..exceptions import BackendError, BackendTimeoutError, BackendConnectionError
from ..logging import get_backend_logger


class BackendStatus(str, Enum):
    """Backend status enumeration."""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class LLMResponse(BaseModel):
    """Standard response format from LLM backends."""
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    
    # Streaming support
    is_partial: bool = False
    delta: Optional[str] = None
    
    # Response metadata
    response_time: Optional[float] = None
    backend_metadata: Dict[str, Any] = {}


class LLMRequest(BaseModel):
    """Standard request format for LLM backends."""
    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    model: Optional[str] = None
    
    # Generation parameters
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    
    # Streaming and formatting
    stream: bool = True
    response_format: Optional[Dict[str, Any]] = None
    
    # Backend-specific parameters
    backend_params: Dict[str, Any] = {}


@dataclass
class BackendInfo:
    """Information about a backend instance."""
    name: str
    backend_type: str
    host: str
    port: int
    model: Optional[str] = None
    status: BackendStatus = BackendStatus.UNKNOWN
    version: Optional[str] = None
    capabilities: List[str] = None
    last_check: Optional[float] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class LLMBackend(ABC):
    """
    Abstract base class for all LLM backends.
    
    All backends must implement this interface to ensure consistent
    behavior across different LLM providers.
    """
    
    def __init__(self, config: Dict[str, Any], name: Optional[str] = None):
        self.config = config
        self.name = name or self.backend_type
        self.logger = get_backend_logger(self.name)
        self._status = BackendStatus.UNKNOWN
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
        self._connection_timeout = 30  # seconds
        self._request_timeout = 300  # seconds
        
    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return the backend type identifier."""
        pass
    
    @property
    def status(self) -> BackendStatus:
        """Get current backend status."""
        return self._status
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend connection."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up backend resources."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        request: LLMRequest
    ) -> AsyncGenerator[LLMResponse, None]:
        """
        Generate response from the LLM.
        
        Args:
            request: The LLM request containing messages, tools, and parameters
            
        Yields:
            LLMResponse objects, potentially multiple for streaming responses
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is healthy and responsive.
        
        Returns:
            True if backend is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """
        Get list of available models for this backend.
        
        Returns:
            List of model names/identifiers
        """
        pass
    
    async def get_info(self) -> BackendInfo:
        """Get detailed backend information."""
        return BackendInfo(
            name=self.name,
            backend_type=self.backend_type,
            host=self.config.get("host", "unknown"),
            port=self.config.get("port", 0),
            model=self.config.get("model"),
            status=self._status,
            last_check=self._last_health_check
        )
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the backend.
        
        Returns:
            Dictionary with test results including timing and status
        """
        start_time = time.time()
        
        try:
            self.logger.info("Testing backend connection", backend=self.name)
            
            # Perform health check
            is_healthy = await asyncio.wait_for(
                self.health_check(),
                timeout=self._connection_timeout
            )
            
            response_time = time.time() - start_time
            
            if is_healthy:
                self._status = BackendStatus.AVAILABLE
                result = {
                    "success": True,
                    "response_time": response_time,
                    "message": f"Backend {self.name} is healthy",
                    "backend": self.name
                }
                self.logger.info("Backend connection test successful", 
                               backend=self.name, 
                               response_time=response_time)
            else:
                self._status = BackendStatus.UNAVAILABLE
                result = {
                    "success": False,
                    "response_time": response_time,
                    "error": f"Backend {self.name} health check failed",
                    "backend": self.name
                }
                self.logger.warning("Backend connection test failed", 
                                  backend=self.name)
            
            return result
            
        except asyncio.TimeoutError:
            self._status = BackendStatus.ERROR
            result = {
                "success": False,
                "response_time": time.time() - start_time,
                "error": f"Backend {self.name} connection timeout",
                "backend": self.name
            }
            self.logger.error("Backend connection timeout", backend=self.name)
            return result
            
        except Exception as e:
            self._status = BackendStatus.ERROR
            result = {
                "success": False,
                "response_time": time.time() - start_time,
                "error": f"Backend {self.name} connection error: {str(e)}",
                "backend": self.name
            }
            self.logger.error("Backend connection error", 
                            backend=self.name, 
                            error=str(e),
                            error_type=type(e).__name__)
            return result
    
    async def periodic_health_check(self) -> None:
        """Perform periodic health checks if needed."""
        current_time = time.time()
        
        if current_time - self._last_health_check > self._health_check_interval:
            try:
                is_healthy = await self.health_check()
                if is_healthy:
                    self._status = BackendStatus.AVAILABLE
                else:
                    self._status = BackendStatus.UNAVAILABLE
                    
                self._last_health_check = current_time
                
            except Exception as e:
                self._status = BackendStatus.ERROR
                self.logger.error("Periodic health check failed",
                                backend=self.name,
                                error=str(e))
    
    def _prepare_request(self, request: LLMRequest) -> LLMRequest:
        """Prepare request with backend-specific defaults."""
        # Apply backend-specific defaults
        if request.model is None:
            request.model = self.config.get("model")
        
        if request.temperature is None:
            request.temperature = self.config.get("temperature", 0.1)
        
        if request.max_tokens is None:
            request.max_tokens = self.config.get("max_tokens", 4096)
        
        return request
    
    def _create_error_response(self, error: Exception) -> LLMResponse:
        """Create an error response from an exception."""
        return LLMResponse(
            content=f"Error: {str(error)}",
            finish_reason="error",
            backend_metadata={
                "error_type": type(error).__name__,
                "backend": self.name
            }
        )
    
    async def _handle_request_with_retry(
        self,
        request: LLMRequest,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> AsyncGenerator[LLMResponse, None]:
        """Handle request with retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                async for response in self.generate(request):
                    yield response
                return
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Request attempt {attempt + 1} failed",
                                  backend=self.name,
                                  error=str(e),
                                  attempt=attempt + 1,
                                  max_retries=max_retries)
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    # Final attempt failed
                    self.logger.error("All request attempts failed",
                                    backend=self.name,
                                    error=str(last_error),
                                    attempts=max_retries)
                    yield self._create_error_response(last_error)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, status={self.status.value})"


class BackendPool:
    """
    Pool of backend instances with load balancing and failover.
    """
    
    def __init__(self, backends: List[LLMBackend]):
        self.backends = backends
        self.logger = get_backend_logger("pool")
        self._current_index = 0
    
    def get_healthy_backends(self) -> List[LLMBackend]:
        """Get list of currently healthy backends."""
        return [b for b in self.backends if b.status == BackendStatus.AVAILABLE]
    
    def get_next_backend(self) -> Optional[LLMBackend]:
        """Get the next available backend using round-robin."""
        healthy_backends = self.get_healthy_backends()
        
        if not healthy_backends:
            return None
        
        backend = healthy_backends[self._current_index % len(healthy_backends)]
        self._current_index += 1
        
        return backend
    
    def get_preferred_backend(self, preferred_types: List[str]) -> Optional[LLMBackend]:
        """Get the most preferred available backend."""
        healthy_backends = self.get_healthy_backends()
        
        # Try to find backend in preferred order
        for preferred_type in preferred_types:
            for backend in healthy_backends:
                if backend.backend_type == preferred_type:
                    return backend
        
        # Fallback to any healthy backend
        return healthy_backends[0] if healthy_backends else None
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all backends."""
        results = {}
        
        tasks = []
        for backend in self.backends:
            task = asyncio.create_task(backend.health_check())
            tasks.append((backend.name, task))
        
        for name, task in tasks:
            try:
                result = await task
                results[name] = result
            except Exception as e:
                results[name] = False
                self.logger.error(f"Health check failed for {name}", error=str(e))
        
        return results
    
    async def cleanup_all(self) -> None:
        """Clean up all backends."""
        tasks = [backend.cleanup() for backend in self.backends]
        await asyncio.gather(*tasks, return_exceptions=True)