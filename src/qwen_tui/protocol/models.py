from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..backends.base import LLMRequest, LLMResponse


class GenerateRequest(BaseModel):
    """WebSocket message to request LLM generation."""

    action: str = "generate"
    request_id: Optional[str] = None
    request: LLMRequest


class GenerateResponse(BaseModel):
    """Streaming response chunk from backend."""

    action: str = "chunk"
    request_id: Optional[str] = None
    response: LLMResponse


class ToolRequest(BaseModel):
    """WebSocket message to invoke a tool."""

    action: str = "tool"
    call_id: Optional[str] = None
    name: str
    parameters: Dict[str, Any] = {}


class ToolResponse(BaseModel):
    """Response to a tool invocation."""

    action: str = "tool_result"
    call_id: Optional[str] = None
    result: Dict[str, Any]
