"""
LM Studio backend implementation for Qwen-TUI.

Provides integration with LM Studio's OpenAI-compatible API with automatic
model discovery, hot-swap detection, and GUI state synchronization.
"""
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import time

from .base import LLMBackend, LLMRequest, LLMResponse, BackendStatus, BackendInfo
from ..exceptions import BackendError, BackendConnectionError, BackendTimeoutError
from ..config import LMStudioConfig


class LMStudioBackend(LLMBackend):
    """LM Studio backend using OpenAI-compatible API."""
    
    def __init__(self, config: LMStudioConfig, name: str = "lm_studio"):
        super().__init__(config.dict(), name)
        self.lm_studio_config = config
        self.base_url = f"http://{config.host}:{config.port}/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[Dict[str, Any]] = []
        self._model_cache_time = 0
        self._model_cache_ttl = 60  # 1 minute (LM Studio can change models frequently)
        self._current_model: Optional[str] = None
        
    @property
    def backend_type(self) -> str:
        return "lm_studio"
    
    async def initialize(self) -> None:
        """Initialize the LM Studio backend."""
        self.logger.info("Initializing LM Studio backend", 
                        host=self.lm_studio_config.host,
                        port=self.lm_studio_config.port)
        
        # Create HTTP session with headers for OpenAI compatibility
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add API key if provided
        if self.lm_studio_config.api_key:
            headers["Authorization"] = f"Bearer {self.lm_studio_config.api_key}"
        
        timeout = aiohttp.ClientTimeout(total=self._connection_timeout)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        )
        
        # Test connection and get initial model info
        try:
            await self.health_check()
            await self._refresh_model_cache()
            self._status = BackendStatus.CONNECTED
            self.logger.info("LM Studio backend initialized successfully")
        except Exception as e:
            self._status = BackendStatus.ERROR
            self.logger.error("Failed to initialize LM Studio backend", error=str(e))
            raise BackendConnectionError(
                f"Failed to connect to LM Studio at {self.base_url}",
                backend_name=self.name,
                cause=e
            )
    
    async def cleanup(self) -> None:
        """Clean up LM Studio backend resources."""
        if self.session:
            await self.session.close()
            self.session = None
        self._status = BackendStatus.DISCONNECTED
        self.logger.info("LM Studio backend cleaned up")
    
    async def health_check(self) -> bool:
        """Check if LM Studio is healthy and responsive."""
        if not self.session:
            return False
        
        try:
            # Try the models endpoint as a health check
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    self._status = BackendStatus.AVAILABLE
                    return True
                else:
                    self._status = BackendStatus.UNAVAILABLE
                    return False
        except Exception as e:
            self.logger.debug("LM Studio health check failed", error=str(e))
            self._status = BackendStatus.ERROR
            return False
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models from LM Studio."""
        await self._refresh_model_cache_if_needed()
        return [model["id"] for model in self._available_models]
    
    async def get_detailed_models(self) -> List[Dict[str, Any]]:
        """Get detailed model information from LM Studio."""
        await self._refresh_model_cache_if_needed()
        return self._available_models.copy()
    
    async def _refresh_model_cache_if_needed(self) -> None:
        """Refresh model cache if it's stale."""
        current_time = time.time()
        if (current_time - self._model_cache_time) > self._model_cache_ttl:
            await self._refresh_model_cache()
    
    async def _refresh_model_cache(self) -> None:
        """Refresh the model cache from LM Studio."""
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    self._available_models = data.get("data", [])
                    self._model_cache_time = time.time()
                    
                    # Detect currently loaded model (usually the first one, or one marked as default)
                    if self._available_models:
                        # LM Studio typically returns the currently loaded model first
                        self._current_model = self._available_models[0]["id"]
                        self.logger.debug("Detected current LM Studio model", 
                                        model=self._current_model)
                else:
                    raise BackendError(
                        f"Failed to get models: HTTP {response.status}",
                        backend_name=self.name
                    )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to LM Studio: {str(e)}",
                backend_name=self.name,
                cause=e
            )
    
    async def get_info(self) -> BackendInfo:
        """Get detailed backend information."""
        info = await super().get_info()
        
        try:
            # Get current model info
            await self._refresh_model_cache_if_needed()
            
            if self._current_model:
                info.model = self._current_model
            
            # Add model count and capabilities
            model_count = len(self._available_models)
            info.capabilities = [f"models: {model_count}"]
            
            # Add first few model names for preview
            if self._available_models:
                model_names = [m["id"] for m in self._available_models[:3]]
                info.capabilities.extend(model_names)
                if len(self._available_models) > 3:
                    info.capabilities.append(f"... +{len(self._available_models) - 3} more")
            
        except Exception as e:
            info.error_message = str(e)
        
        return info
    
    async def generate(self, request: LLMRequest) -> AsyncGenerator[LLMResponse, None]:
        """Generate response using LM Studio."""
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        
        # Prepare request
        request = self._prepare_request(request)
        
        # Convert request to OpenAI format
        openai_request = await self._convert_to_openai_request(request)
        
        self.logger.info("Sending request to LM Studio",
                        model=request.model or "current",
                        messages=len(request.messages),
                        tools=len(request.tools) if request.tools else 0)
        
        start_time = time.time()
        
        try:
            endpoint = "/chat/completions"
            
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=openai_request,
                timeout=aiohttp.ClientTimeout(total=self._request_timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise BackendError(
                        f"LM Studio request failed: HTTP {response.status} - {error_text}",
                        backend_name=self.name
                    )
                
                if request.stream:
                    # Handle streaming response
                    async for chunk in self._handle_streaming_response(response, start_time):
                        yield chunk
                else:
                    # Handle non-streaming response
                    data = await response.json()
                    yield self._convert_from_openai_response(data, start_time)
                    
        except asyncio.TimeoutError:
            raise BackendTimeoutError(
                f"LM Studio request timed out after {self._request_timeout}s",
                backend_name=self.name
            )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to LM Studio: {str(e)}",
                backend_name=self.name,
                cause=e
            )
    
    async def _convert_to_openai_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Convert LLMRequest to OpenAI API format."""
        openai_request = {
            "messages": request.messages,
            "stream": request.stream,
        }
        
        # Add model if specified, otherwise use current model
        if request.model:
            openai_request["model"] = request.model
        elif self._current_model:
            openai_request["model"] = self._current_model
        else:
            # If no model specified and none detected, let LM Studio use its current model
            pass
        
        # Add generation parameters
        if request.temperature is not None:
            openai_request["temperature"] = request.temperature
        
        if request.max_tokens is not None:
            openai_request["max_tokens"] = request.max_tokens
        
        if request.top_p is not None:
            openai_request["top_p"] = request.top_p
        
        if request.frequency_penalty is not None:
            openai_request["frequency_penalty"] = request.frequency_penalty
        
        if request.presence_penalty is not None:
            openai_request["presence_penalty"] = request.presence_penalty
        
        # Add tools if present (function calling)
        if request.tools:
            openai_request["tools"] = request.tools
            openai_request["tool_choice"] = "auto"
        
        # Add response format if specified
        if request.response_format:
            openai_request["response_format"] = request.response_format
        
        # Add backend-specific parameters
        if request.backend_params:
            openai_request.update(request.backend_params)
        
        return openai_request
    
    def _convert_from_openai_response(self, data: Dict[str, Any], start_time: float) -> LLMResponse:
        """Convert OpenAI response to LLMResponse format."""
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content="",
                finish_reason="error",
                backend_metadata={"error": "No choices in response", "backend": self.name}
            )
        
        choice = choices[0]
        message = choice.get("message", {})
        
        # Extract tool calls if present
        tool_calls = None
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
        
        # Extract usage information
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model"),
            response_time=time.time() - start_time,
            backend_metadata={
                "backend": self.name,
                "object": data.get("object"),
                "created": data.get("created"),
                "system_fingerprint": data.get("system_fingerprint")
            }
        )
    
    async def _handle_streaming_response(
        self, 
        response: aiohttp.ClientResponse, 
        start_time: float
    ) -> AsyncGenerator[LLMResponse, None]:
        """Handle streaming response from LM Studio."""
        buffer = ""
        
        async for chunk in response.content.iter_any():
            buffer += chunk.decode('utf-8', errors='ignore')
            
            # Process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if not line or not line.startswith('data: '):
                    continue
                
                # Remove 'data: ' prefix
                data_str = line[6:]
                
                # Check for end of stream
                if data_str == '[DONE]':
                    break
                
                try:
                    data = json.loads(data_str)
                    
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    
                    # Convert to standard response format
                    response_obj = self._convert_from_openai_response(data, start_time)
                    
                    # Mark as partial and set delta content
                    if "content" in delta:
                        response_obj.is_partial = True
                        response_obj.delta = delta["content"]
                        response_obj.content = delta["content"]
                    
                    # Handle tool calls in streaming
                    if "tool_calls" in delta:
                        response_obj.tool_calls = delta["tool_calls"]
                    
                    yield response_obj
                    
                    # Break if this is the final chunk
                    if choice.get("finish_reason"):
                        break
                        
                except json.JSONDecodeError as e:
                    self.logger.warning("Failed to parse streaming response chunk",
                                      chunk=data_str,
                                      error=str(e))
                    continue
    
    async def switch_model(self, model_id: str) -> bool:
        """
        Attempt to switch the active model in LM Studio.
        
        Note: LM Studio doesn't have a direct API to switch models,
        but we can detect when the user manually switches in the GUI.
        """
        self.logger.info("Model switching requested", 
                        current_model=self._current_model,
                        requested_model=model_id)
        
        # Clear cache to force refresh on next request
        self._model_cache_time = 0
        
        # LM Studio requires manual model switching through the GUI
        # We can only detect the change and update our cache
        await self._refresh_model_cache()
        
        if self._current_model == model_id:
            self.logger.info("Model switch detected", model=model_id)
            return True
        else:
            self.logger.warning("Model switch not detected - manual switch required in LM Studio GUI",
                              requested=model_id,
                              current=self._current_model)
            return False
    
    async def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        await self._refresh_model_cache_if_needed()
        
        for model in self._available_models:
            if model["id"] == model_id:
                return model
        
        return None
    
    async def is_model_loaded(self, model_id: str) -> bool:
        """Check if a specific model is currently loaded."""
        await self._refresh_model_cache_if_needed()
        return self._current_model == model_id