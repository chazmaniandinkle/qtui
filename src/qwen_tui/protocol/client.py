"""Client for interacting with the protocol server."""

import json
from typing import Any, AsyncGenerator, Dict

import aiohttp

from ..backends.base import LLMRequest, LLMResponse
from ..logging import get_main_logger


class ProtocolClient:
    """WebSocket client used by ThinkingManager when protocol mode is enabled."""

    def __init__(self, url: str = "ws://localhost:8765/ws"):
        self.url = url
        self.logger = get_main_logger()

    async def generate(self, request: LLMRequest) -> AsyncGenerator[LLMResponse, None]:
        """Send a generation request and yield streaming responses."""
        session = aiohttp.ClientSession()
        async with session.ws_connect(self.url) as ws:
            await ws.send_json({"action": "generate", "request": request.model_dump()})
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("action") == "chunk":
                        yield LLMResponse(**data["response"])
                    if data.get("action") == "done":
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        await session.close()

    async def call_tool(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool on the server."""
        session = aiohttp.ClientSession()
        async with session.ws_connect(self.url) as ws:
            await ws.send_json(
                {"action": "tool", "name": name, "parameters": parameters}
            )
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                result = data.get("result", {})
            else:
                result = {"status": "error", "error": "no response"}
        await session.close()
        return result
