"""
MCP tool adapter for integrating MCP tools with the existing tool system.

Provides a seamless adapter that wraps MCP tools to conform to the BaseTool
interface, enabling MCP tools to work transparently with the existing agent
and tool execution infrastructure.
"""
import time
from typing import Any, Dict, List, Optional

from ..tools.base import BaseTool, ToolResult, ToolStatus
from ..logging import get_main_logger
from .client import MCPClient
from .models import MCPTool, MCPToolCallResult
from .exceptions import MCPToolExecutionError, handle_mcp_error


class MCPToolAdapter(BaseTool):
    """
    Adapter that wraps MCP tools to conform to BaseTool interface.
    
    This allows MCP tools to be used transparently within the existing
    tool system, with full support for permissions, validation, and
    error handling.
    """
    
    def __init__(self, mcp_tool: MCPTool, client: MCPClient, server_name: str):
        """
        Initialize MCP tool adapter.
        
        Args:
            mcp_tool: MCP tool definition
            client: MCP client for communication
            server_name: Name of the MCP server
        """
        self.mcp_tool = mcp_tool
        self.client = client
        self.server_name = server_name
        
        # Initialize base tool with MCP tool info
        super().__init__(
            name=f"mcp_{server_name}_{mcp_tool.name}",
            description=f"[MCP:{server_name}] {mcp_tool.description}"
        )
        
        self.logger = get_main_logger()
        self._schema_cache: Optional[Dict[str, Any]] = None
    
    @property
    def original_name(self) -> str:
        """Get the original MCP tool name (without prefix)."""
        return self.mcp_tool.name
    
    @property
    def is_available(self) -> bool:
        """Check if the MCP tool is available."""
        return self.client.is_connected
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the MCP tool.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult: Execution result
        """
        start_time = time.time()
        
        try:
            # Ensure client is connected
            if not self.client.is_connected:
                try:
                    await self.client.connect()
                except Exception as e:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.ERROR,
                        error=f"Failed to connect to MCP server {self.server_name}: {e}",
                        execution_time=time.time() - start_time
                    )
            
            # Validate and prepare arguments
            validated_args = self._prepare_arguments(kwargs)
            
            self.logger.debug(
                f"Executing MCP tool: {self.original_name} on {self.server_name}",
                arguments=validated_args
            )
            
            # Execute tool via MCP client
            mcp_result = await self.client.call_tool(self.original_name, validated_args)
            
            # Convert MCP result to ToolResult
            result = self._convert_mcp_result(mcp_result, time.time() - start_time)
            
            self.logger.debug(
                f"MCP tool completed: {self.original_name}",
                status=result.status.value,
                execution_time=result.execution_time
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(
                f"MCP tool failed: {self.original_name} on {self.server_name}",
                error=error_msg,
                execution_time=execution_time
            )
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=error_msg,
                execution_time=execution_time,
                metadata={
                    "server_name": self.server_name,
                    "original_name": self.original_name,
                    "error_type": type(e).__name__
                }
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for tool parameters.
        
        Returns:
            Dict[str, Any]: JSON schema for parameters
        """
        if self._schema_cache is None:
            self._schema_cache = self.mcp_tool.to_openai_function_schema()
        
        return self._schema_cache
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters against the MCP tool schema.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValueError: If validation fails
        """
        schema = self.get_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # Check required parameters
        for param in required:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")
        
        # Check parameter types and constraints
        for param_name, param_value in parameters.items():
            if param_name in properties:
                param_schema = properties[param_name]
                self._validate_parameter_value(param_name, param_value, param_schema)
        
        return True
    
    def _prepare_arguments(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare and validate arguments for MCP tool execution.
        
        Args:
            kwargs: Raw arguments
            
        Returns:
            Dict[str, Any]: Validated arguments
        """
        # Remove any internal parameters
        args = {k: v for k, v in kwargs.items() if not k.startswith('_')}
        
        # Validate against schema
        self.validate_parameters(args)
        
        return args
    
    def _validate_parameter_value(
        self, 
        param_name: str, 
        value: Any, 
        schema: Dict[str, Any]
    ) -> None:
        """Validate individual parameter value against schema."""
        param_type = schema.get("type", "string")
        
        # Basic type validation
        if param_type == "string" and not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                raise ValueError(f"Parameter '{param_name}' must be a string")
        elif param_type == "integer" and not isinstance(value, int):
            try:
                value = int(value)
            except Exception:
                raise ValueError(f"Parameter '{param_name}' must be an integer")
        elif param_type == "number" and not isinstance(value, (int, float)):
            try:
                value = float(value)
            except Exception:
                raise ValueError(f"Parameter '{param_name}' must be a number")
        elif param_type == "boolean" and not isinstance(value, bool):
            if value in ("true", "false", "True", "False", 1, 0):
                value = value in ("true", "True", 1)
            else:
                raise ValueError(f"Parameter '{param_name}' must be a boolean")
        
        # Enum validation
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(
                f"Parameter '{param_name}' must be one of: {schema['enum']}"
            )
    
    def _convert_mcp_result(
        self, 
        mcp_result: MCPToolCallResult, 
        execution_time: float
    ) -> ToolResult:
        """
        Convert MCP tool result to ToolResult format.
        
        Args:
            mcp_result: MCP tool execution result
            execution_time: Execution time in seconds
            
        Returns:
            ToolResult: Converted result
        """
        if mcp_result.isError:
            # Error result
            error_message = self._extract_error_message(mcp_result)
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=error_message,
                execution_time=execution_time,
                metadata={
                    "server_name": self.server_name,
                    "original_name": self.original_name,
                    "mcp_content": mcp_result.content
                }
            )
        else:
            # Success result
            result_data = self._extract_result_data(mcp_result)
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_data,
                execution_time=execution_time,
                metadata={
                    "server_name": self.server_name,
                    "original_name": self.original_name,
                    "content_items": len(mcp_result.content)
                }
            )
    
    def _extract_error_message(self, mcp_result: MCPToolCallResult) -> str:
        """Extract error message from MCP result."""
        error_parts = []
        
        for item in mcp_result.content:
            if item.get("type") == "text":
                error_parts.append(item.get("text", ""))
            elif item.get("type") == "error":
                error_parts.append(item.get("error", ""))
        
        if error_parts:
            return "\n".join(error_parts)
        else:
            return f"MCP tool {self.original_name} failed with unknown error"
    
    def _extract_result_data(self, mcp_result: MCPToolCallResult) -> Any:
        """Extract result data from successful MCP execution."""
        if len(mcp_result.content) == 0:
            return None
        elif len(mcp_result.content) == 1:
            # Single content item
            item = mcp_result.content[0]
            if item.get("type") == "text":
                return item.get("text", "")
            else:
                return item
        else:
            # Multiple content items
            text_parts = []
            other_items = []
            
            for item in mcp_result.content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                else:
                    other_items.append(item)
            
            if text_parts and not other_items:
                # Only text content
                return "\n".join(text_parts)
            elif other_items and not text_parts:
                # Only non-text content
                return other_items if len(other_items) > 1 else other_items[0]
            else:
                # Mixed content
                return {
                    "text": "\n".join(text_parts) if text_parts else None,
                    "data": other_items if other_items else None,
                    "all_content": mcp_result.content
                }
    
    def get_mcp_tool_info(self) -> Dict[str, Any]:
        """Get information about the underlying MCP tool."""
        return {
            "server_name": self.server_name,
            "original_name": self.original_name,
            "description": self.mcp_tool.description,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.type,
                    "description": param.description,
                    "required": param.required,
                    "default": param.default
                }
                for param in self.mcp_tool.parameters
            ],
            "metadata": self.mcp_tool.metadata,
            "is_available": self.is_available
        }
    
    def __repr__(self) -> str:
        return f"MCPToolAdapter(name='{self.name}', server='{self.server_name}', original='{self.original_name}')"


class MCPToolRegistry:
    """
    Registry for managing MCP tool adapters.
    
    Provides centralized management of MCP tools, including discovery,
    registration, and lifecycle management.
    """
    
    def __init__(self):
        self.adapters: Dict[str, MCPToolAdapter] = {}
        self.servers: Dict[str, MCPClient] = {}
        self.logger = get_main_logger()
    
    def register_server(self, client: MCPClient) -> None:
        """Register an MCP client."""
        self.servers[client.server_name] = client
        self.logger.debug(f"Registered MCP server: {client.server_name}")
    
    async def discover_and_register_tools(self, server_name: str) -> List[MCPToolAdapter]:
        """
        Discover tools from an MCP server and register adapters.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List[MCPToolAdapter]: Registered tool adapters
        """
        client = self.servers.get(server_name)
        if not client:
            raise ValueError(f"MCP server not registered: {server_name}")
        
        try:
            # Discover tools
            tools = await client.list_tools()
            adapters = []
            
            for tool in tools:
                # Create adapter
                adapter = MCPToolAdapter(tool, client, server_name)
                
                # Register adapter
                self.adapters[adapter.name] = adapter
                adapters.append(adapter)
                
                self.logger.debug(f"Registered MCP tool: {adapter.name}")
            
            self.logger.info(f"Registered {len(adapters)} tools from MCP server: {server_name}")
            return adapters
            
        except Exception as e:
            self.logger.error(f"Failed to discover tools from {server_name}: {e}")
            raise
    
    def get_adapter(self, tool_name: str) -> Optional[MCPToolAdapter]:
        """Get MCP tool adapter by name."""
        return self.adapters.get(tool_name)
    
    def get_adapters_by_server(self, server_name: str) -> List[MCPToolAdapter]:
        """Get all adapters from a specific server."""
        return [
            adapter for adapter in self.adapters.values()
            if adapter.server_name == server_name
        ]
    
    def list_adapters(self) -> List[MCPToolAdapter]:
        """Get all registered adapters."""
        return list(self.adapters.values())
    
    def remove_server_tools(self, server_name: str) -> int:
        """
        Remove all tools from a specific server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            int: Number of tools removed
        """
        to_remove = [
            name for name, adapter in self.adapters.items()
            if adapter.server_name == server_name
        ]
        
        for name in to_remove:
            del self.adapters[name]
        
        if to_remove:
            self.logger.info(f"Removed {len(to_remove)} tools from server: {server_name}")
        
        return len(to_remove)
    
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered servers."""
        status = {}
        
        for server_name, client in self.servers.items():
            adapters = self.get_adapters_by_server(server_name)
            status[server_name] = {
                "connected": client.is_connected,
                "tool_count": len(adapters),
                "tools": [adapter.original_name for adapter in adapters]
            }
        
        return status