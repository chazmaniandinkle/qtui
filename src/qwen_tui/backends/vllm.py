"""vLLM backend implementation."""
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
import aiohttp
import time

from .base import LLMBackend, LLMRequest, LLMResponse, BackendStatus, BackendInfo
from ..exceptions import BackendError, BackendConnectionError, BackendTimeoutError
from ..config import VLLMConfig


class VLLMBackend(LLMBackend):
    """vLLM backend using OpenAI-compatible API."""

    def __init__(self, config: VLLMConfig, name: str = "vllm"):
        super().__init__(config.dict(), name)
        self.vllm_config = config
        self.base_url = f"http://{config.host}:{config.port}/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[str] = []
        self._model_cache_time = 0
        self._model_cache_ttl = 300

    @property
    def backend_type(self) -> str:
        return "vllm"

    async def initialize(self) -> None:
        self.logger.info("Initializing vLLM backend", host=self.vllm_config.host, port=self.vllm_config.port)
        timeout = aiohttp.ClientTimeout(total=self._connection_timeout)
        # Allow proxy environment variables to be honored for outbound requests.
        self.session = aiohttp.ClientSession(timeout=timeout, trust_env=True)
        try:
            await self.health_check()
            self._status = BackendStatus.CONNECTED
            self.logger.info("vLLM backend initialized")
        except Exception as e:
            if self.session:
                await self.session.close()
                self.session = None
            self._status = BackendStatus.ERROR
            self.logger.error("Failed to initialize vLLM backend", error=str(e))
            raise BackendConnectionError(
                f"Failed to connect to vLLM at {self.base_url}",
                backend_name=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        self._status = BackendStatus.DISCONNECTED
        self.logger.info("vLLM backend cleaned up")

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
            self.logger.debug("vLLM health check failed", error=str(e))
            self._status = BackendStatus.ERROR
            return False

    async def get_available_models(self) -> List[str]:
        current_time = time.time()
        if (current_time - self._model_cache_time) < self._model_cache_ttl and self._available_models:
            return self._available_models
        if not self.session:
            raise BackendConnectionError("Backend not initialized", backend_name=self.name)
        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    self._available_models = models
                    self._model_cache_time = current_time
                    return models
                else:
                    raise BackendError(
                        f"Failed to get models: HTTP {response.status}",
                        backend_name=self.name,
                    )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to vLLM: {str(e)}",
                backend_name=self.name,
                cause=e,
            )

    async def get_info(self) -> BackendInfo:
        info = await super().get_info()
        try:
            models = await self.get_available_models()
            info.capabilities = [f"models: {len(models)}"] + models[:5]
            if models:
                info.model = models[0]
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
        if request.model:
            openai_request["model"] = request.model
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
                        f"vLLM request failed: HTTP {response.status} - {error_text}",
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
                f"vLLM request timed out after {self._request_timeout}s",
                backend_name=self.name,
            )
        except aiohttp.ClientError as e:
            raise BackendConnectionError(
                f"Failed to connect to vLLM: {str(e)}",
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
                    if "tool_calls" in delta:
                        resp.tool_calls = delta["tool_calls"]
                    yield resp
                    if choice.get("finish_reason"):
                        break
                except json.JSONDecodeError:
                    continue


