"""
Model Context Protocol (MCP) integration for Qwen-TUI.

This module provides MCP client implementation and tool adapters to seamlessly
integrate MCP servers with the existing tool system.
"""

from .client import MCPClient
from .adapter import MCPToolAdapter
from .models import MCPTool, MCPRequest, MCPResponse, MCPServerConfig
from .discovery import MCPServerDiscovery
from .exceptions import MCPError, MCPConnectionError, MCPProtocolError, MCPServerError
from .integration import MCPIntegrationManager, initialize_mcp_from_config, shutdown_mcp

__all__ = [
    "MCPClient",
    "MCPToolAdapter", 
    "MCPTool",
    "MCPRequest",
    "MCPResponse",
    "MCPServerConfig",
    "MCPServerDiscovery",
    "MCPError",
    "MCPConnectionError",
    "MCPProtocolError", 
    "MCPServerError",
    "MCPIntegrationManager",
    "initialize_mcp_from_config",
    "shutdown_mcp",
]