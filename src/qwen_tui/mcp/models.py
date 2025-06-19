"""
MCP protocol models and data structures.

Defines the core data structures for MCP communication, tool definitions,
and server configurations.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MCPMessageType(str, Enum):
    """MCP message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class MCPMethod(str, Enum):
    """MCP method names."""
    INITIALIZE = "initialize"
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"
    PING = "ping"
    SHUTDOWN = "shutdown"


class MCPError(BaseModel):
    """MCP error object."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPRequest(BaseModel):
    """MCP request message."""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP response message."""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Any] = None
    error: Optional[MCPError] = None


class MCPNotification(BaseModel):
    """MCP notification message."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPToolParameter(BaseModel):
    """MCP tool parameter definition."""
    name: str
    type: str
    description: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    parameters: List[MCPToolParameter] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None

    def to_openai_function_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description or ""
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False
        }

    def to_qwen_tool_schema(self) -> Dict[str, Any]:
        """Convert to Qwen-TUI tool schema format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.to_openai_function_schema(),
            "metadata": self.metadata or {}
        }


class MCPToolCall(BaseModel):
    """MCP tool call request."""
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    """MCP tool execution result."""
    content: List[Dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
    
    def get_text_content(self) -> str:
        """Extract text content from result."""
        text_parts = []
        for item in self.content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "\n".join(text_parts)
    
    def get_error_message(self) -> Optional[str]:
        """Extract error message if this is an error result."""
        if not self.isError:
            return None
        
        error_parts = []
        for item in self.content:
            if item.get("type") == "text":
                error_parts.append(item.get("text", ""))
        return "\n".join(error_parts) if error_parts else "Unknown error"


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str
    url: str
    enabled: bool = True
    tools: Optional[List[str]] = None  # Specific tools to load, None = all
    timeout: int = 30
    auth: Optional[Dict[str, str]] = None
    retry_attempts: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 60  # seconds
    
    def get_connection_url(self) -> str:
        """Get the WebSocket connection URL."""
        if self.url.startswith("ws://") or self.url.startswith("wss://"):
            return self.url
        elif self.url.startswith("http://"):
            return self.url.replace("http://", "ws://", 1)
        elif self.url.startswith("https://"):
            return self.url.replace("https://", "wss://", 1)
        else:
            # Assume it's a host:port
            return f"ws://{self.url}"


class MCPServerInfo(BaseModel):
    """Information about an MCP server."""
    name: str
    version: str
    protocol_version: str = "1.0.0"
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    

class MCPServerStatus(str, Enum):
    """MCP server connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


class MCPServerState(BaseModel):
    """Current state of an MCP server."""
    config: MCPServerConfig
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    info: Optional[MCPServerInfo] = None
    tools: List[MCPTool] = Field(default_factory=list)
    last_error: Optional[str] = None
    last_connected: Optional[float] = None  # Unix timestamp
    connection_attempts: int = 0


class MCPInitializeParams(BaseModel):
    """Parameters for MCP initialize request."""
    protocolVersion: str = "1.0.0"
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    clientInfo: Dict[str, str] = Field(default_factory=lambda: {
        "name": "qwen-tui",
        "version": "1.0.0"
    })


class MCPInitializeResult(BaseModel):
    """Result of MCP initialize request."""
    protocolVersion: str
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    serverInfo: MCPServerInfo


class MCPToolsListResult(BaseModel):
    """Result of MCP tools/list request."""
    tools: List[MCPTool]


class MCPToolCallParams(BaseModel):
    """Parameters for MCP tools/call request."""
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResult(BaseModel):
    """Result of MCP tools/call request."""
    content: List[Dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
    
    def get_text_content(self) -> str:
        """Extract text content from result."""
        text_parts = []
        for item in self.content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "\n".join(text_parts)
    
    def get_error_message(self) -> Optional[str]:
        """Extract error message if this is an error result."""
        if not self.isError:
            return None
        
        error_parts = []
        for item in self.content:
            if item.get("type") == "text":
                error_parts.append(item.get("text", ""))
        return "\n".join(error_parts) if error_parts else "Unknown error"
    
    def to_mcp_tool_result(self) -> MCPToolResult:
        """Convert to MCPToolResult."""
        return MCPToolResult(content=self.content, isError=self.isError)