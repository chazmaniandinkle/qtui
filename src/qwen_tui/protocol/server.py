"""Simple protocol server exposing backend and tool operations over WebSocket."""
import json
from typing import Any

from aiohttp import web

from ..backends.manager import BackendManager
from ..logging import get_main_logger
from ..tools import ToolManager
from .models import GenerateRequest, ToolRequest


class ProtocolServer:
    """WebSocket server handling LLM and tool requests."""

    def __init__(
        self,
        backend_manager: BackendManager,
        tool_manager: ToolManager,
        host: str = "0.0.0.0",
        port: int = 8765,
    ):
        self.backend_manager = backend_manager
        self.tool_manager = tool_manager
        self.host = host
        self.port = port
        self.logger = get_main_logger()
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app["backend_manager"] = self.backend_manager
        app["tool_manager"] = self.tool_manager
        app.router.add_get("/ws", self._ws_handler)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self.logger.info("Protocol server started", host=self.host, port=self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self.logger.info("Protocol server stopped")

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        backend_manager: BackendManager = request.app["backend_manager"]
        tool_manager: ToolManager = request.app["tool_manager"]

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    action = data.get("action")
                    if action == "generate":
                        g_req = GenerateRequest(**data)
                        llm_req = g_req.request
                        async for resp in backend_manager.generate(llm_req):
                            await ws.send_json(
                                {
                                    "action": "chunk",
                                    "request_id": g_req.request_id,
                                    "response": resp.model_dump(),
                                }
                            )
                        await ws.send_json(
                            {"action": "done", "request_id": g_req.request_id}
                        )
                    elif action == "tool":
                        t_req = ToolRequest(**data)
                        result = await tool_manager.registry.execute_tool(
                            t_req.name, t_req.parameters
                        )
                        await ws.send_json(
                            {
                                "action": "tool_result",
                                "call_id": t_req.call_id,
                                "result": result.to_dict(),
                            }
                        )
                except Exception as e:
                    await ws.send_json({"action": "error", "error": str(e)})
            elif msg.type == web.WSMsgType.ERROR:
                break
        return ws
