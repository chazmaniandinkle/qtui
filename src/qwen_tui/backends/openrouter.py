"""OpenRouter backend implementation."""
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import time

from .base import LLMBackend, LLMRequest, LLMResponse, BackendStatus, BackendInfo
from ..exceptions import BackendError, BackendConnectionError, BackendTimeoutError
from ..config import OpenRouterConfig


class OpenRouterBackend(LLMBackend):
    """Backend for OpenRouter cloud service."""

    def __init__(self, config: OpenRouterConfig, name: str = "openrouter"):
        super().__init__(config.dict(), name)
        self.openrouter_config = config
        self.base_url = config.base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[Dict[str, Any]] = []
        self._model_cache_time = 0
        self._model_cache_ttl = 600

    @property
    def backend_type(self) -> str:
        return "openrouter"

    async def initialize(self) -> None:
        headers = {
            "Authorization": f"Bearer {self.openrouter_config.api_key}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self._connection_timeout)
        # Enable proxy usage via environment variables so that the backend works
        # in restricted network environments where direct access is blocked.
        self.session = aiohttp.ClientSession(
            timeout=timeout, headers=headers, trust_env=True
        )
        try:
            await self.health_check()
            self._status = BackendStatus.CONNECTED
            self.logger.info("OpenRouter backend initialized")
        except Exception as e:
            # Ensure the session is closed if initialization fails to avoid
            # leaking open connections in tests and during runtime.
            if self.session:
                await self.session.close()
                self.session = None
            self._status = BackendStatus.ERROR
            self.logger.error(
                "Failed to initialize OpenRouter backend", error=str(e)
            )
            raise BackendConnectionError(
                f"Failed to connect to OpenRouter at {self.base_url}",
                backend_name=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        self._status = BackendStatus.DISCONNECTED
        self.logger.info("OpenRouter backend cleaned up")

    async def health_check(self) -> bool:
        if not self.session:
            return False
        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    self._status = BackendStatus.AVAILABLE
                    return True
                else:
                    self._status = BackendStatus.UNAVAILABLE
                    return False
        except Exception as e:
            self.logger.debug("OpenRouter health check failed", error=str(e))
            self._status = BackendStatus.ERROR
            return False

    async def get_available_models(self) -> List[str]:
        current_time = time.time()
        if (current_time - self._model_cache_time) < self._model_cache_ttl and self._available_models:
            return [m["id"] for m in self._available_models]
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    self._available_models = data.get("data", [])
                    self._model_cache_time = current_time
                    return [m["id"] for m in self._available_models]
                else:
                    raise BackendError(
                        f"Failed to get models: HTTP {response.status}",
                        backend_name=self.name,
                    )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to OpenRouter: {str(e)}",
                backend_name=self.name,
                cause=e,
            )

    async def get_detailed_models(self) -> List[Dict[str, Any]]:
        await self.get_available_models()
        return self._available_models.copy()

    async def get_info(self) -> BackendInfo:
        info = await super().get_info()
        try:
            models = await self.get_available_models()
            info.capabilities = [f"models: {len(models)}"]
            if models:
                info.model = self.openrouter_config.model
        except Exception as e:
            info.error_message = str(e)
        return info

    async def generate(self, request: LLMRequest) -> AsyncGenerator[LLMResponse, None]:
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        request = self._prepare_request(request)
        openai_request = {
            "messages": request.messages,
            "stream": request.stream,
        }
        openai_request["model"] = request.model or self.openrouter_config.model
        if request.temperature is not None:
            openai_request["temperature"] = request.temperature
        if request.max_tokens is not None:
            openai_request["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            openai_request["top_p"] = request.top_p
        if request.tools:
            openai_request["tools"] = request.tools
            openai_request["tool_choice"] = "auto"
        if request.response_format:
            openai_request["response_format"] = request.response_format
        if request.backend_params:
            openai_request.update(request.backend_params)
        self.logger.debug("OpenRouter request payload", payload=openai_request)
        start_time = time.time()
        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=openai_request,
                timeout=aiohttp.ClientTimeout(total=self._request_timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise BackendError(
                        f"OpenRouter request failed: HTTP {response.status} - {error_text}",
                        backend_name=self.name,
                    )
                if request.stream:
                    async for chunk in self._handle_streaming_response(response, start_time):
                        yield chunk
                else:
                    data = await response.json()
                    yield self._convert_from_openai_response(data, start_time)
        except asyncio.TimeoutError:
            raise BackendTimeoutError(
                f"OpenRouter request timed out after {self._request_timeout}s",
                backend_name=self.name,
            )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to OpenRouter: {str(e)}",
                backend_name=self.name,
                cause=e,
            )

    def _convert_from_openai_response(self, data: Dict[str, Any], start_time: float) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content="",
                finish_reason="error",
                backend_metadata={"error": "No choices", "backend": self.name},
            )
        choice = choices[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls")
        usage = data.get("usage")
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model"),
            response_time=time.time() - start_time,
            backend_metadata={"backend": self.name},
        )

    async def _handle_streaming_response(
        self, response: aiohttp.ClientResponse, start_time: float
    ) -> AsyncGenerator[LLMResponse, None]:
        buffer = ""
        async for chunk in response.content.iter_any():
            self.logger.debug("Received stream chunk", size=len(chunk))
            buffer += chunk.decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    resp = self._convert_from_openai_response(data, start_time)
                    if "content" in delta:
                        resp.is_partial = True
                        resp.delta = delta["content"]
                        resp.content = delta["content"]
                        self.logger.debug("Streaming delta", delta=resp.delta)
                    if "tool_calls" in delta:
                        resp.tool_calls = delta["tool_calls"]
                        self.logger.debug("Streaming tool calls", calls=resp.tool_calls)
                    yield resp
                    if choice.get("finish_reason"):
                        break
                except json.JSONDecodeError:
                    continue


