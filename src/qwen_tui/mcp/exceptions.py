"""
MCP-specific exceptions that extend the base exception hierarchy.

These exceptions integrate with the existing error handling system
while providing MCP-specific error context.
"""
from typing import Any, Dict, Optional

from ..exceptions import QwenTUIError


class MCPError(QwenTUIError):
    """Base class for MCP-related errors."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.server_name = server_name
        self.method = method
        context = context or {}
        if server_name:
            context["server"] = server_name
        if method:
            context["method"] = method
        super().__init__(message, context, cause)


class MCPConnectionError(MCPError):
    """Error connecting to MCP server."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.url = url
        context = context or {}
        if url:
            context["url"] = url
        super().__init__(message, server_name, "connect", context, cause)


class MCPProtocolError(MCPError):
    """MCP protocol-level error."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        error_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.error_code = error_code
        context = context or {}
        if error_code is not None:
            context["error_code"] = error_code
        super().__init__(message, server_name, method, context, cause)


class MCPServerError(MCPError):
    """Error returned by MCP server."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        error_code: Optional[int] = None,
        error_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.error_data = error_data
        context = context or {}
        if error_code is not None:
            context["error_code"] = error_code
        if error_data:
            context["error_data"] = error_data
        super().__init__(message, server_name, method, context, cause)


class MCPTimeoutError(MCPError):
    """MCP request timed out."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        timeout: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.timeout = timeout
        context = context or {}
        if timeout is not None:
            context["timeout"] = timeout
        super().__init__(message, server_name, method, context, cause)


class MCPToolNotFoundError(MCPError):
    """Requested MCP tool not found."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.tool_name = tool_name
        context = context or {}
        if tool_name:
            context["tool"] = tool_name
        super().__init__(message, server_name, "tools/call", context, cause)


class MCPToolExecutionError(MCPError):
    """Error executing MCP tool."""
    
    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.tool_name = tool_name
        context = context or {}
        if tool_name:
            context["tool"] = tool_name
        super().__init__(message, server_name, "tools/call", context, cause)


class MCPDiscoveryError(MCPError):
    """Error during MCP server discovery."""
    pass


class MCPValidationError(MCPError):
    """MCP data validation error."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.field = field
        self.value = value
        context = context or {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)
        super().__init__(message, None, "validation", context, cause)


def handle_mcp_error(
    error: Exception,
    server_name: str,
    method: Optional[str] = None,
    operation: str = "MCP operation"
) -> MCPError:
    """Convert generic exceptions to appropriate MCP errors."""
    context = {"operation": operation}
    
    if isinstance(error, MCPError):
        return error
    elif (isinstance(error, ConnectionError) or 
          "connection" in str(error).lower() or
          "connect" in str(error).lower() or
          "Cannot connect" in str(error)):
        return MCPConnectionError(
            f"Failed to connect to MCP server {server_name}",
            server_name=server_name,
            context=context,
            cause=error
        )
    elif isinstance(error, TimeoutError) or "timeout" in str(error).lower():
        return MCPTimeoutError(
            f"Request to MCP server {server_name} timed out",
            server_name=server_name,
            method=method,
            context=context,
            cause=error
        )
    elif "protocol" in str(error).lower() or "jsonrpc" in str(error).lower():
        return MCPProtocolError(
            f"Protocol error with MCP server {server_name}: {error}",
            server_name=server_name,
            method=method,
            context=context,
            cause=error
        )
    else:
        return MCPError(
            f"Error communicating with MCP server {server_name}: {error}",
            server_name=server_name,
            method=method,
            context=context,
            cause=error
        )