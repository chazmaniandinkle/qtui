"""
Integration utilities for MCP with the existing Qwen-TUI infrastructure.

Provides helper functions and utilities for integrating MCP tools
with the existing tool registry, permission system, and application lifecycle.
"""
import asyncio
from typing import List, Optional

from ..config import Config, MCPServerConfig
from ..logging import get_main_logger
from .discovery import MCPServerDiscovery, initialize_mcp_discovery, shutdown_mcp_discovery
from .models import MCPServerConfig as MCPServerConfigModel


logger = get_main_logger()


async def initialize_mcp_from_config(config: Config) -> Optional[MCPServerDiscovery]:
    """
    Initialize MCP integration based on configuration.
    
    Args:
        config: Application configuration
        
    Returns:
        MCPServerDiscovery instance if MCP is enabled and configured
    """
    if not config.mcp.enabled:
        logger.info("MCP integration is disabled")
        return None
    
    if not config.mcp.servers:
        logger.info("No MCP servers configured")
        return None
    
    try:
        # Convert config servers to MCP server configs
        server_configs = []
        for server_config in config.mcp.servers:
            mcp_config = MCPServerConfigModel(
                name=server_config.name,
                url=server_config.url,
                enabled=server_config.enabled,
                tools=server_config.tools,
                timeout=server_config.timeout,
                auth=server_config.auth,
                retry_attempts=server_config.retry_attempts,
                retry_delay=server_config.retry_delay,
                health_check_interval=server_config.health_check_interval
            )
            server_configs.append(mcp_config)
        
        # Initialize discovery service
        discovery_service = await initialize_mcp_discovery(server_configs)
        
        logger.info(f"MCP integration initialized with {len(server_configs)} servers")
        return discovery_service
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP integration: {e}")
        return None


async def shutdown_mcp() -> None:
    """Shutdown MCP integration."""
    try:
        await shutdown_mcp_discovery()
        logger.info("MCP integration shutdown complete")
    except Exception as e:
        logger.error(f"Error during MCP shutdown: {e}")


def create_sample_mcp_config() -> List[MCPServerConfig]:
    """
    Create sample MCP server configurations for testing.
    
    Returns:
        List of sample MCP server configurations
    """
    return [
        MCPServerConfig(
            name="filesystem",
            url="ws://localhost:3001",
            enabled=True,
            tools=["read_file", "write_file", "list_directory"],
            timeout=30
        ),
        MCPServerConfig(
            name="web_tools",
            url="ws://localhost:3002", 
            enabled=True,
            tools=["fetch_url", "search_web"],
            timeout=60
        ),
        MCPServerConfig(
            name="git_tools",
            url="ws://localhost:3003",
            enabled=False,  # Disabled by default
            tools=None,  # Load all tools
            timeout=30
        )
    ]


async def test_mcp_integration() -> bool:
    """
    Test MCP integration functionality.
    
    Returns:
        bool: True if test passes
    """
    try:
        logger.info("Testing MCP integration...")
        
        # Create test configuration
        test_configs = create_sample_mcp_config()
        
        # Initialize discovery service
        discovery_service = MCPServerDiscovery(test_configs)
        
        # Test discovery service creation
        assert discovery_service is not None
        logger.info("✓ Discovery service created")
        
        # Test configuration handling
        server_status = await discovery_service.get_all_server_status()
        assert isinstance(server_status, dict)
        logger.info("✓ Server status retrieval works")
        
        # Test tool registry integration
        tool_registry = discovery_service.get_tool_registry()
        assert tool_registry is not None
        logger.info("✓ Tool registry integration works")
        
        logger.info("✓ MCP integration test passed")
        return True
        
    except Exception as e:
        logger.error(f"MCP integration test failed: {e}")
        return False


class MCPIntegrationManager:
    """
    Manager for MCP integration lifecycle.
    
    Handles initialization, shutdown, and runtime management of MCP
    integration with the Qwen-TUI application.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.discovery_service: Optional[MCPServerDiscovery] = None
        self.logger = get_main_logger()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize MCP integration.
        
        Returns:
            bool: True if initialization successful
        """
        if self._initialized:
            return True
        
        try:
            self.discovery_service = await initialize_mcp_from_config(self.config)
            self._initialized = True  # Always consider initialized, even if MCP is disabled
            
            if self.discovery_service is not None:
                self.logger.info("MCP integration manager initialized")
            else:
                self.logger.info("MCP integration not enabled or configured")
            
            return self._initialized
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP integration manager: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown MCP integration."""
        if self._initialized:
            await shutdown_mcp()
            self.discovery_service = None
            self._initialized = False
            self.logger.info("MCP integration manager shutdown")
    
    def is_enabled(self) -> bool:
        """Check if MCP integration is enabled and initialized."""
        return self._initialized and self.discovery_service is not None
    
    async def get_available_tools(self) -> List:
        """Get available MCP tools."""
        if not self.is_enabled():
            return []
        
        try:
            return await self.discovery_service.get_available_tools()
        except Exception as e:
            self.logger.error(f"Failed to get available MCP tools: {e}")
            return []
    
    async def get_server_status(self) -> dict:
        """Get status of all MCP servers."""
        if not self.is_enabled():
            return {"enabled": False}
        
        try:
            return await self.discovery_service.get_all_server_status()
        except Exception as e:
            self.logger.error(f"Failed to get MCP server status: {e}")
            return {"enabled": True, "error": str(e)}
    
    async def connect_server(self, server_name: str) -> bool:
        """Connect to a specific MCP server."""
        if not self.is_enabled():
            return False
        
        try:
            return await self.discovery_service.connect_server(server_name)
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return False
    
    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from a specific MCP server."""
        if not self.is_enabled():
            return False
        
        try:
            return await self.discovery_service.disconnect_server(server_name)
        except Exception as e:
            self.logger.error(f"Failed to disconnect from MCP server {server_name}: {e}")
            return False
    
    async def refresh_server_tools(self, server_name: str) -> List:
        """Refresh tools from a specific server."""
        if not self.is_enabled():
            return []
        
        try:
            return await self.discovery_service.refresh_server_tools(server_name)
        except Exception as e:
            self.logger.error(f"Failed to refresh tools from {server_name}: {e}")
            return []
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()


# Global integration manager instance
_global_integration_manager: Optional[MCPIntegrationManager] = None


def get_integration_manager() -> Optional[MCPIntegrationManager]:
    """Get the global MCP integration manager."""
    return _global_integration_manager


def set_integration_manager(manager: MCPIntegrationManager) -> None:
    """Set the global MCP integration manager."""
    global _global_integration_manager
    _global_integration_manager = manager


async def initialize_global_mcp_integration(config: Config) -> MCPIntegrationManager:
    """
    Initialize the global MCP integration manager.
    
    Args:
        config: Application configuration
        
    Returns:
        MCPIntegrationManager: Initialized manager
    """
    global _global_integration_manager
    
    if _global_integration_manager:
        await _global_integration_manager.shutdown()
    
    _global_integration_manager = MCPIntegrationManager(config)
    await _global_integration_manager.initialize()
    
    return _global_integration_manager


async def shutdown_global_mcp_integration() -> None:
    """Shutdown the global MCP integration manager."""
    global _global_integration_manager
    
    if _global_integration_manager:
        await _global_integration_manager.shutdown()
        _global_integration_manager = None