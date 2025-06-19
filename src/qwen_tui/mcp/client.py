"""
MCP client implementation for connecting to MCP servers.

Extends the existing ProtocolClient to provide MCP-specific functionality
while maintaining compatibility with the existing WebSocket infrastructure.
"""
import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
import time

import aiohttp

from ..logging import get_main_logger
from ..protocol.client import ProtocolClient
from .models import (
    MCPRequest, MCPResponse, MCPServerConfig, MCPServerInfo, MCPTool,
    MCPInitializeParams, MCPInitializeResult, MCPToolsListResult,
    MCPToolCallParams, MCPToolCallResult, MCPMethod, MCPServerStatus
)
from .exceptions import (
    MCPConnectionError, MCPProtocolError, MCPServerError, MCPTimeoutError,
    MCPToolNotFoundError, MCPToolExecutionError, handle_mcp_error
)


class MCPClient:
    """
    MCP client for connecting to and communicating with MCP servers.
    
    Provides high-level methods for tool discovery, execution, and server management
    while handling connection management, error recovery, and protocol details.
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.logger = get_main_logger()
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._server_info: Optional[MCPServerInfo] = None
        self._tools: List[MCPTool] = []
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._connection_lock = asyncio.Lock()
        self._last_ping = 0.0
        
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to MCP server."""
        return self._connected and self._ws is not None and not self._ws.closed
    
    @property
    def server_name(self) -> str:
        """Get server name for error reporting."""
        return self.config.name
    
    async def connect(self) -> MCPServerInfo:
        """
        Connect to the MCP server and perform initialization handshake.
        
        Returns:
            MCPServerInfo: Server information from initialization
            
        Raises:
            MCPConnectionError: If connection fails
            MCPProtocolError: If initialization fails
        """
        async with self._connection_lock:
            if self.is_connected:
                return self._server_info
            
            try:
                # Create session if needed
                if self._session is None:
                    self._session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                    )
                
                # Connect to WebSocket
                url = self.config.get_connection_url()
                self.logger.info(f"Connecting to MCP server: {self.server_name} at {url}")
                
                self._ws = await self._session.ws_connect(
                    url,
                    heartbeat=30,
                    headers=self._get_auth_headers()
                )
                
                # Start message handler
                asyncio.create_task(self._message_handler())
                
                # Perform initialization handshake
                self._server_info = await self._initialize()
                self._connected = True
                
                self.logger.info(f"Successfully connected to MCP server: {self.server_name}")
                return self._server_info
                
            except Exception as e:
                await self._cleanup_connection()
                raise handle_mcp_error(e, self.server_name, "connect", "connection")
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        async with self._connection_lock:
            if self.is_connected:
                try:
                    # Send shutdown notification
                    await self._send_notification(MCPMethod.SHUTDOWN)
                except Exception:
                    pass  # Ignore errors during shutdown
                
            await self._cleanup_connection()
            self.logger.info(f"Disconnected from MCP server: {self.server_name}")
    
    async def list_tools(self) -> List[MCPTool]:
        """
        Get list of available tools from the MCP server.
        
        Returns:
            List[MCPTool]: Available tools
            
        Raises:
            MCPConnectionError: If not connected
            MCPProtocolError: If request fails
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            request = MCPRequest(
                id=self._generate_id(),
                method=MCPMethod.LIST_TOOLS
            )
            
            response = await self._send_request(request)
            result = MCPToolsListResult(**response.result)
            
            # Filter tools if specific tools are configured
            if self.config.tools:
                filtered_tools = [
                    tool for tool in result.tools 
                    if tool.name in self.config.tools
                ]
                self._tools = filtered_tools
            else:
                self._tools = result.tools
            
            self.logger.debug(f"Retrieved {len(self._tools)} tools from {self.server_name}")
            return self._tools
            
        except Exception as e:
            raise handle_mcp_error(e, self.server_name, MCPMethod.LIST_TOOLS, "list_tools")
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """
        Execute a tool on the MCP server.
        
        Args:
            name: Tool name to execute
            arguments: Tool arguments
            
        Returns:
            MCPToolCallResult: Tool execution result
            
        Raises:
            MCPToolNotFoundError: If tool not found
            MCPToolExecutionError: If tool execution fails
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            # Validate tool exists
            if not any(tool.name == name for tool in self._tools):
                available_tools = [tool.name for tool in self._tools]
                raise MCPToolNotFoundError(
                    f"Tool '{name}' not found on server {self.server_name}. "
                    f"Available tools: {available_tools}",
                    server_name=self.server_name,
                    tool_name=name
                )
            
            request = MCPRequest(
                id=self._generate_id(),
                method=MCPMethod.CALL_TOOL,
                params=MCPToolCallParams(name=name, arguments=arguments).model_dump()
            )
            
            self.logger.debug(f"Calling tool '{name}' on {self.server_name}", arguments=arguments)
            
            response = await self._send_request(request)
            
            if response.error:
                raise MCPToolExecutionError(
                    f"Tool '{name}' execution failed: {response.error.message}",
                    server_name=self.server_name,
                    tool_name=name
                )
            
            result = MCPToolCallResult(**response.result)
            self.logger.debug(f"Tool '{name}' completed successfully")
            
            return result
            
        except (MCPToolNotFoundError, MCPToolExecutionError):
            raise
        except Exception as e:
            raise handle_mcp_error(e, self.server_name, MCPMethod.CALL_TOOL, f"call_tool:{name}")
    
    async def ping(self) -> bool:
        """
        Send ping to check server connectivity.
        
        Returns:
            bool: True if server responds to ping
        """
        if not self.is_connected:
            return False
        
        try:
            request = MCPRequest(
                id=self._generate_id(),
                method=MCPMethod.PING
            )
            
            await self._send_request(request, timeout=5.0)
            self._last_ping = time.time()
            return True
            
        except Exception:
            return False
    
    async def get_server_info(self) -> Optional[MCPServerInfo]:
        """Get server information."""
        return self._server_info
    
    async def get_tools(self) -> List[MCPTool]:
        """Get cached tools list."""
        if not self._tools:
            await self.list_tools()
        return self._tools
    
    async def _initialize(self) -> MCPServerInfo:
        """Perform MCP initialization handshake."""
        params = MCPInitializeParams(
            capabilities={
                "tools": {"enabled": True}
            }
        )
        
        request = MCPRequest(
            id=self._generate_id(),
            method=MCPMethod.INITIALIZE,
            params=params.model_dump()
        )
        
        response = await self._send_request(request)
        
        if response.error:
            raise MCPProtocolError(
                f"Initialization failed: {response.error.message}",
                server_name=self.server_name,
                method=MCPMethod.INITIALIZE,
                error_code=response.error.code
            )
        
        result = MCPInitializeResult(**response.result)
        return result.serverInfo
    
    async def _send_request(
        self, 
        request: MCPRequest, 
        timeout: Optional[float] = None
    ) -> MCPResponse:
        """Send request and wait for response."""
        if not self.is_connected:
            raise MCPConnectionError(
                f"Not connected to MCP server {self.server_name}",
                server_name=self.server_name
            )
        
        timeout = timeout or self.config.timeout
        request_id = str(request.id)
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            # Send request
            await self._ws.send_str(request.model_dump_json())
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            raise MCPTimeoutError(
                f"Request timed out after {timeout}s",
                server_name=self.server_name,
                method=request.method,
                timeout=timeout
            )
        except Exception as e:
            raise handle_mcp_error(e, self.server_name, request.method, "send_request")
        finally:
            self._pending_requests.pop(request_id, None)
    
    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send notification (no response expected)."""
        if not self.is_connected:
            return
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        try:
            await self._ws.send_str(json.dumps(notification))
        except Exception as e:
            self.logger.warning(f"Failed to send notification: {e}")
    
    async def _message_handler(self):
        """Handle incoming messages from MCP server."""
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON from {self.server_name}: {e}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket error from {self.server_name}: {self._ws.exception()}")
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                    self.logger.info(f"WebSocket closed for {self.server_name}")
                    break
        except Exception as e:
            self.logger.error(f"Message handler error for {self.server_name}: {e}")
        finally:
            self._connected = False
            # Cancel any pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle individual message from server."""
        if "id" in data:
            # Response to request
            response = MCPResponse(**data)
            request_id = str(response.id)
            
            if request_id in self._pending_requests:
                future = self._pending_requests[request_id]
                if not future.done():
                    future.set_result(response)
        else:
            # Notification or other message
            self.logger.debug(f"Received notification from {self.server_name}: {data}")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers if configured."""
        if self.config.auth:
            return self.config.auth.copy()
        return {}
    
    def _generate_id(self) -> str:
        """Generate unique request ID."""
        return str(uuid.uuid4())
    
    async def _cleanup_connection(self):
        """Clean up connection resources."""
        self._connected = False
        
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


class MCPClientPool:
    """
    Pool of MCP clients for managing multiple server connections.
    
    Provides connection management, health monitoring, and load balancing
    across multiple MCP servers.
    """
    
    def __init__(self, configs: List[MCPServerConfig]):
        self.configs = {config.name: config for config in configs if config.enabled}
        self.clients: Dict[str, MCPClient] = {}
        self.logger = get_main_logger()
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize all clients and start health monitoring."""
        for name, config in self.configs.items():
            client = MCPClient(config)
            self.clients[name] = client
            
            # Try to connect
            try:
                await client.connect()
                self.logger.info(f"Initialized MCP client: {name}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize MCP client {name}: {e}")
        
        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())
    
    async def shutdown(self):
        """Shutdown all clients and stop monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        for client in self.clients.values():
            try:
                await client.disconnect()
            except Exception as e:
                self.logger.warning(f"Error disconnecting client: {e}")
    
    async def get_client(self, server_name: str) -> Optional[MCPClient]:
        """Get client by server name."""
        return self.clients.get(server_name)
    
    async def get_all_tools(self) -> Dict[str, List[MCPTool]]:
        """Get tools from all connected servers."""
        all_tools = {}
        for name, client in self.clients.items():
            if client.is_connected:
                try:
                    tools = await client.get_tools()
                    all_tools[name] = tools
                except Exception as e:
                    self.logger.warning(f"Failed to get tools from {name}: {e}")
        return all_tools
    
    async def call_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> MCPToolCallResult:
        """Call tool on specific server."""
        client = self.clients.get(server_name)
        if not client:
            raise MCPConnectionError(f"MCP server not found: {server_name}")
        
        return await client.call_tool(tool_name, arguments)
    
    async def _health_monitor(self):
        """Monitor health of all clients."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for name, client in self.clients.items():
                    if client.is_connected:
                        # Ping server
                        if not await client.ping():
                            self.logger.warning(f"MCP server {name} failed ping, reconnecting...")
                            try:
                                await client.connect()
                            except Exception as e:
                                self.logger.error(f"Failed to reconnect to {name}: {e}")
                    else:
                        # Try to reconnect
                        try:
                            await client.connect()
                            self.logger.info(f"Reconnected to MCP server: {name}")
                        except Exception:
                            pass  # Will try again next cycle
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()