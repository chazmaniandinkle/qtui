"""
MCP server discovery and management.

Provides functionality for discovering, connecting to, and managing
multiple MCP servers with health monitoring and automatic recovery.
"""
import asyncio
from typing import Dict, List, Optional, Set
import time

from ..logging import get_main_logger
from .client import MCPClient, MCPClientPool
from .adapter import MCPToolAdapter, MCPToolRegistry
from .models import MCPServerConfig, MCPServerStatus, MCPServerState
from .exceptions import MCPConnectionError, MCPDiscoveryError


class MCPServerDiscovery:
    """
    MCP server discovery and management service.
    
    Handles discovery, connection, health monitoring, and lifecycle management
    of MCP servers. Integrates with the tool registry to automatically
    register and unregister tools based on server availability.
    """
    
    def __init__(self, configs: List[MCPServerConfig]):
        self.configs = {config.name: config for config in configs if config.enabled}
        self.states: Dict[str, MCPServerState] = {}
        self.clients: Dict[str, MCPClient] = {}
        self.tool_registry = MCPToolRegistry()
        self.logger = get_main_logger()
        
        # Background tasks
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._discovery_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Initialize server states
        for name, config in self.configs.items():
            self.states[name] = MCPServerState(
                config=config,
                status=MCPServerStatus.DISCONNECTED
            )
    
    async def start(self) -> None:
        """Start discovery service and background monitoring."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("Starting MCP server discovery service")
        
        # Start background tasks
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        
        # Initial discovery
        await self._discover_all_servers()
    
    async def stop(self) -> None:
        """Stop discovery service and disconnect all servers."""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("Stopping MCP server discovery service")
        
        # Cancel background tasks
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        await self._disconnect_all_servers()
    
    async def get_available_tools(self) -> List[MCPToolAdapter]:
        """Get all available tools from connected servers."""
        return self.tool_registry.list_adapters()
    
    async def get_server_status(self, server_name: str) -> Optional[MCPServerState]:
        """Get status of a specific server."""
        return self.states.get(server_name)
    
    async def get_all_server_status(self) -> Dict[str, MCPServerState]:
        """Get status of all servers."""
        return self.states.copy()
    
    async def connect_server(self, server_name: str) -> bool:
        """
        Manually connect to a specific server.
        
        Args:
            server_name: Name of the server to connect
            
        Returns:
            bool: True if connection successful
        """
        if server_name not in self.configs:
            self.logger.warning(f"Unknown MCP server: {server_name}")
            return False
        
        return await self._connect_server(server_name)
    
    async def disconnect_server(self, server_name: str) -> bool:
        """
        Manually disconnect from a specific server.
        
        Args:
            server_name: Name of the server to disconnect
            
        Returns:
            bool: True if disconnection successful
        """
        if server_name not in self.clients:
            return True
        
        return await self._disconnect_server(server_name)
    
    async def refresh_server_tools(self, server_name: str) -> List[MCPToolAdapter]:
        """
        Refresh tools from a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List[MCPToolAdapter]: Updated tool adapters
        """
        if server_name not in self.clients:
            raise MCPConnectionError(f"Server not connected: {server_name}")
        
        client = self.clients[server_name]
        
        try:
            # Remove existing tools
            self.tool_registry.remove_server_tools(server_name)
            
            # Discover and register new tools
            adapters = await self.tool_registry.discover_and_register_tools(server_name)
            
            # Update server state
            state = self.states[server_name]
            state.tools = await client.get_tools()
            
            self.logger.info(f"Refreshed {len(adapters)} tools from server: {server_name}")
            return adapters
            
        except Exception as e:
            self.logger.error(f"Failed to refresh tools from {server_name}: {e}")
            raise MCPDiscoveryError(f"Failed to refresh tools: {e}")
    
    async def _discover_all_servers(self) -> None:
        """Discover and connect to all configured servers."""
        tasks = []
        for server_name in self.configs.keys():
            task = asyncio.create_task(self._connect_server(server_name))
            tasks.append(task)
        
        if tasks:
            # Connect to servers in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            connected_count = sum(1 for result in results if result is True)
            self.logger.info(f"Initial discovery complete: {connected_count}/{len(tasks)} servers connected")
    
    async def _connect_server(self, server_name: str) -> bool:
        """
        Connect to a specific MCP server.
        
        Args:
            server_name: Name of the server to connect
            
        Returns:
            bool: True if connection successful
        """
        if server_name in self.clients and self.clients[server_name].is_connected:
            return True
        
        config = self.configs[server_name]
        state = self.states[server_name]
        
        # Update status
        state.status = MCPServerStatus.CONNECTING
        state.connection_attempts += 1
        
        try:
            self.logger.debug(f"Connecting to MCP server: {server_name}")
            
            # Create client
            client = MCPClient(config)
            
            # Connect and initialize
            server_info = await client.connect()
            
            # Register client
            self.clients[server_name] = client
            self.tool_registry.register_server(client)
            
            # Update state
            state.status = MCPServerStatus.CONNECTED
            state.info = server_info
            state.last_connected = time.time()
            state.last_error = None
            
            # Discover and register tools
            try:
                adapters = await self.tool_registry.discover_and_register_tools(server_name)
                state.tools = await client.get_tools()
                
                self.logger.info(
                    f"Connected to MCP server: {server_name} "
                    f"({len(adapters)} tools available)"
                )
                
            except Exception as e:
                self.logger.warning(f"Failed to discover tools from {server_name}: {e}")
                # Continue with connection even if tool discovery fails
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.logger.warning(f"Failed to connect to MCP server {server_name}: {error_msg}")
            
            # Update state
            state.status = MCPServerStatus.ERROR
            state.last_error = error_msg
            
            # Clean up partial connection
            if server_name in self.clients:
                try:
                    await self.clients[server_name].disconnect()
                except Exception:
                    pass
                del self.clients[server_name]
            
            return False
    
    async def _disconnect_server(self, server_name: str) -> bool:
        """
        Disconnect from a specific MCP server.
        
        Args:
            server_name: Name of the server to disconnect
            
        Returns:
            bool: True if disconnection successful
        """
        if server_name not in self.clients:
            return True
        
        client = self.clients[server_name]
        state = self.states[server_name]
        
        try:
            # Disconnect client
            await client.disconnect()
            
            # Remove tools
            removed_count = self.tool_registry.remove_server_tools(server_name)
            
            # Update state
            state.status = MCPServerStatus.DISCONNECTED
            state.tools = []
            state.last_error = None
            
            # Remove client
            del self.clients[server_name]
            
            self.logger.info(f"Disconnected from MCP server: {server_name} ({removed_count} tools removed)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from {server_name}: {e}")
            state.last_error = str(e)
            return False
    
    async def _disconnect_all_servers(self) -> None:
        """Disconnect from all servers."""
        tasks = []
        for server_name in list(self.clients.keys()):
            task = asyncio.create_task(self._disconnect_server(server_name))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _discovery_loop(self) -> None:
        """Background discovery loop for reconnecting to failed servers."""
        while self._running:
            try:
                # Wait between discovery cycles
                await asyncio.sleep(30)
                
                # Check for disconnected servers
                for server_name, state in self.states.items():
                    if (state.status == MCPServerStatus.DISCONNECTED or 
                        state.status == MCPServerStatus.ERROR):
                        
                        # Check if we should retry
                        if state.connection_attempts < state.config.retry_attempts:
                            # Wait for retry delay
                            if state.last_error:
                                await asyncio.sleep(state.config.retry_delay)
                            
                            # Attempt reconnection
                            await self._connect_server(server_name)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Discovery loop error: {e}")
    
    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        while self._running:
            try:
                # Wait between health checks
                await asyncio.sleep(60)
                
                # Check health of connected servers
                for server_name, client in list(self.clients.items()):
                    if client.is_connected:
                        # Ping server
                        if not await client.ping():
                            self.logger.warning(
                                f"MCP server {server_name} failed health check, reconnecting..."
                            )
                            
                            # Mark as error and trigger reconnection
                            state = self.states[server_name]
                            state.status = MCPServerStatus.ERROR
                            state.last_error = "Health check failed"
                            
                            # Disconnect and let discovery loop reconnect
                            await self._disconnect_server(server_name)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    def get_tool_registry(self) -> MCPToolRegistry:
        """Get the tool registry for direct access."""
        return self.tool_registry
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Global discovery service instance
_global_discovery_service: Optional[MCPServerDiscovery] = None


def get_discovery_service() -> Optional[MCPServerDiscovery]:
    """Get the global MCP discovery service instance."""
    return _global_discovery_service


def set_discovery_service(service: MCPServerDiscovery) -> None:
    """Set the global MCP discovery service instance."""
    global _global_discovery_service
    _global_discovery_service = service


async def initialize_mcp_discovery(configs: List[MCPServerConfig]) -> MCPServerDiscovery:
    """
    Initialize and start the global MCP discovery service.
    
    Args:
        configs: List of MCP server configurations
        
    Returns:
        MCPServerDiscovery: Initialized discovery service
    """
    global _global_discovery_service
    
    if _global_discovery_service:
        await _global_discovery_service.stop()
    
    _global_discovery_service = MCPServerDiscovery(configs)
    await _global_discovery_service.start()
    
    return _global_discovery_service


async def shutdown_mcp_discovery() -> None:
    """Shutdown the global MCP discovery service."""
    global _global_discovery_service
    
    if _global_discovery_service:
        await _global_discovery_service.stop()
        _global_discovery_service = None