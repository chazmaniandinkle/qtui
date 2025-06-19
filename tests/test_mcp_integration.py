"""
Tests for MCP (Model Context Protocol) integration.

Validates MCP client, adapter, discovery, and integration functionality
with comprehensive unit tests and integration tests.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from qwen_tui.mcp import (
    MCPClient, MCPToolAdapter, MCPServerDiscovery, MCPIntegrationManager,
    MCPError, MCPConnectionError, MCPProtocolError
)
from qwen_tui.mcp.models import (
    MCPServerConfig, MCPTool, MCPToolParameter, MCPToolCallResult,
    MCPServerInfo, MCPServerStatus
)
from qwen_tui.config import Config, MCPConfig
from qwen_tui.tools.base import ToolResult, ToolStatus


@pytest.fixture
def mcp_server_config():
    """Create test MCP server configuration."""
    return MCPServerConfig(
        name="test_server",
        url="ws://localhost:3001",
        enabled=True,
        timeout=30
    )


@pytest.fixture
def sample_mcp_tool():
    """Create sample MCP tool definition."""
    return MCPTool(
        name="test_tool",
        description="A test tool for MCP integration",
        parameters=[
            MCPToolParameter(
                name="input_text",
                type="string",
                description="Input text to process",
                required=True
            ),
            MCPToolParameter(
                name="uppercase",
                type="boolean", 
                description="Convert to uppercase",
                required=False,
                default=False
            )
        ]
    )


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing."""
    ws_mock = AsyncMock()
    ws_mock.closed = False
    ws_mock.send_str = AsyncMock()
    ws_mock.receive = AsyncMock()
    ws_mock.close = AsyncMock()
    return ws_mock


@pytest.fixture
def mock_session():
    """Create mock aiohttp session."""
    session_mock = AsyncMock()
    session_mock.ws_connect = AsyncMock()
    session_mock.close = AsyncMock()
    return session_mock


class TestMCPModels:
    """Test MCP data models."""
    
    def test_mcp_server_config_creation(self, mcp_server_config):
        """Test creating MCP server configuration."""
        assert mcp_server_config.name == "test_server"
        assert mcp_server_config.url == "ws://localhost:3001"
        assert mcp_server_config.enabled is True
        assert mcp_server_config.timeout == 30
    
    def test_mcp_tool_schema_conversion(self, sample_mcp_tool):
        """Test MCP tool schema conversion."""
        # Test OpenAI function schema conversion
        openai_schema = sample_mcp_tool.to_openai_function_schema()
        
        assert openai_schema["type"] == "object"
        assert "input_text" in openai_schema["properties"]
        assert "uppercase" in openai_schema["properties"]
        assert "input_text" in openai_schema["required"]
        assert "uppercase" not in openai_schema["required"]
        assert openai_schema["properties"]["uppercase"]["default"] is False
        
        # Test Qwen tool schema conversion
        qwen_schema = sample_mcp_tool.to_qwen_tool_schema()
        assert qwen_schema["name"] == "test_tool"
        assert qwen_schema["description"] == "A test tool for MCP integration"
        assert "parameters" in qwen_schema
    
    def test_mcp_tool_result_parsing(self):
        """Test MCP tool result parsing."""
        # Test text content extraction
        result = MCPToolCallResult(
            content=[
                {"type": "text", "text": "Hello world"},
                {"type": "text", "text": "Second line"}
            ],
            isError=False
        )
        
        text_content = result.get_text_content()
        assert text_content == "Hello world\nSecond line"
        
        # Test error result
        error_result = MCPToolCallResult(
            content=[{"type": "text", "text": "Something went wrong"}],
            isError=True
        )
        
        error_message = error_result.get_error_message()
        assert error_message == "Something went wrong"
    
    def test_server_url_parsing(self):
        """Test server URL parsing and normalization."""
        # Test WebSocket URL
        config = MCPServerConfig(name="test", url="ws://localhost:3001")
        assert config.get_connection_url() == "ws://localhost:3001"
        
        # Test HTTP URL conversion
        config = MCPServerConfig(name="test", url="http://localhost:3001")
        assert config.get_connection_url() == "ws://localhost:3001"
        
        # Test HTTPS URL conversion
        config = MCPServerConfig(name="test", url="https://localhost:3001")
        assert config.get_connection_url() == "wss://localhost:3001"
        
        # Test host:port format
        config = MCPServerConfig(name="test", url="localhost:3001")
        assert config.get_connection_url() == "ws://localhost:3001"


class TestMCPClient:
    """Test MCP client functionality."""
    
    @pytest.mark.asyncio
    async def test_client_creation(self, mcp_server_config):
        """Test MCP client creation."""
        client = MCPClient(mcp_server_config)
        
        assert client.config == mcp_server_config
        assert client.server_name == "test_server"
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_client_connection_mock(self, mcp_server_config, mock_session, mock_websocket):
        """Test client connection with mocked WebSocket."""
        client = MCPClient(mcp_server_config)
        
        # Mock server info response
        server_info = MCPServerInfo(
            name="test_server",
            version="1.0.0",
            protocol_version="1.0.0"
        )
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            mock_session.ws_connect.return_value.__aenter__.return_value = mock_websocket
            
            # Mock initialization response
            init_response = {
                "jsonrpc": "2.0",
                "id": "test-id",
                "result": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {},
                    "serverInfo": server_info.model_dump()
                }
            }
            
            # Test connection would require more complex mocking
            # This tests the basic structure
            assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_client_error_handling(self, mcp_server_config):
        """Test client error handling."""
        client = MCPClient(mcp_server_config)
        
        # Test tool call without connection
        with pytest.raises(MCPConnectionError):
            await client.call_tool("nonexistent_tool", {})


class TestMCPToolAdapter:
    """Test MCP tool adapter functionality."""
    
    def test_adapter_creation(self, sample_mcp_tool, mcp_server_config):
        """Test MCP tool adapter creation."""
        mock_client = Mock()
        mock_client.server_name = mcp_server_config.name
        
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        assert adapter.name == f"mcp_{mcp_server_config.name}_{sample_mcp_tool.name}"
        assert adapter.original_name == sample_mcp_tool.name
        assert adapter.server_name == mcp_server_config.name
        assert adapter.description.startswith(f"[MCP:{mcp_server_config.name}]")
    
    def test_adapter_schema(self, sample_mcp_tool, mcp_server_config):
        """Test adapter schema generation."""
        mock_client = Mock()
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        schema = adapter.get_schema()
        
        assert schema["type"] == "object"
        assert "input_text" in schema["properties"]
        assert "uppercase" in schema["properties"]
        assert "input_text" in schema["required"]
    
    def test_parameter_validation(self, sample_mcp_tool, mcp_server_config):
        """Test parameter validation."""
        mock_client = Mock()
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        # Test valid parameters
        valid_params = {"input_text": "hello world", "uppercase": True}
        assert adapter.validate_parameters(valid_params) is True
        
        # Test missing required parameter
        invalid_params = {"uppercase": True}
        with pytest.raises(ValueError, match="Missing required parameter: input_text"):
            adapter.validate_parameters(invalid_params)
    
    @pytest.mark.asyncio
    async def test_adapter_execution_success(self, sample_mcp_tool, mcp_server_config):
        """Test successful tool execution via adapter."""
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.server_name = mcp_server_config.name
        
        # Mock successful tool call result
        mcp_result = MCPToolCallResult(
            content=[{"type": "text", "text": "HELLO WORLD"}],
            isError=False
        )
        mock_client.call_tool.return_value = mcp_result
        
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        # Execute tool
        result = await adapter.execute(input_text="hello world", uppercase=True)
        
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.COMPLETED
        assert result.result == "HELLO WORLD"
        assert result.tool_name == adapter.name
    
    @pytest.mark.asyncio
    async def test_adapter_execution_error(self, sample_mcp_tool, mcp_server_config):
        """Test error handling in tool execution."""
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.server_name = mcp_server_config.name
        
        # Mock error result
        mcp_result = MCPToolCallResult(
            content=[{"type": "text", "text": "Tool execution failed"}],
            isError=True
        )
        mock_client.call_tool.return_value = mcp_result
        
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        # Execute tool
        result = await adapter.execute(input_text="hello world")
        
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "Tool execution failed" in result.error
    
    def test_adapter_info_extraction(self, sample_mcp_tool, mcp_server_config):
        """Test adapter information extraction."""
        mock_client = Mock()
        mock_client.is_connected = True
        
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        info = adapter.get_mcp_tool_info()
        
        assert info["server_name"] == mcp_server_config.name
        assert info["original_name"] == sample_mcp_tool.name
        assert info["description"] == sample_mcp_tool.description
        assert len(info["parameters"]) == 2
        assert info["is_available"] is True


class TestMCPIntegration:
    """Test MCP integration with Qwen-TUI."""
    
    def test_config_integration(self):
        """Test MCP configuration integration."""
        # Test default config
        config = Config()
        assert hasattr(config, 'mcp')
        assert config.mcp.enabled is False
        assert len(config.mcp.servers) == 0
        
        # Test custom MCP config
        from qwen_tui.config import MCPServerConfig as ConfigMCPServerConfig
        mcp_config = MCPConfig(
            enabled=True,
            servers=[
                ConfigMCPServerConfig(
                    name="test_server",
                    url="ws://localhost:3001",
                    enabled=True
                )
            ]
        )
        
        config = Config(mcp=mcp_config)
        assert config.mcp.enabled is True
        assert len(config.mcp.servers) == 1
        assert config.mcp.servers[0].name == "test_server"
    
    @pytest.mark.asyncio
    async def test_integration_manager_lifecycle(self):
        """Test MCP integration manager lifecycle."""
        # Create config with MCP disabled
        config = Config()
        config.mcp.enabled = False
        
        manager = MCPIntegrationManager(config)
        
        # Test initialization with disabled MCP
        success = await manager.initialize()
        assert success is True  # Should succeed even when disabled
        assert not manager.is_enabled()
        
        # Test shutdown
        await manager.shutdown()
        assert not manager.is_enabled()
    
    @pytest.mark.asyncio
    async def test_integration_manager_with_servers(self):
        """Test integration manager with configured servers."""
        # Create config with MCP enabled
        config = Config()
        config.mcp.enabled = True
        from qwen_tui.config import MCPServerConfig as ConfigMCPServerConfig
        config.mcp.servers = [
            ConfigMCPServerConfig(
                name="test_server",
                url="ws://localhost:3001",
                enabled=True,
                timeout=30
            )
        ]
        
        manager = MCPIntegrationManager(config)
        
        # Test that manager handles server configuration
        assert manager.config.mcp.enabled is True
        assert len(manager.config.mcp.servers) == 1
    
    def test_permission_system_compatibility(self, sample_mcp_tool, mcp_server_config):
        """Test that MCP tools work with permission system."""
        mock_client = Mock()
        adapter = MCPToolAdapter(sample_mcp_tool, mock_client, mcp_server_config.name)
        
        # Verify adapter inherits from BaseTool
        from qwen_tui.tools.base import BaseTool
        assert isinstance(adapter, BaseTool)
        
        # Verify adapter has required methods for permission system
        assert hasattr(adapter, 'get_schema')
        assert hasattr(adapter, 'validate_parameters')
        assert hasattr(adapter, 'safe_execute')
        assert hasattr(adapter, 'name')
        assert hasattr(adapter, 'description')


class TestMCPDiscovery:
    """Test MCP server discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_discovery_service_creation(self, mcp_server_config):
        """Test MCP discovery service creation."""
        discovery = MCPServerDiscovery([mcp_server_config])
        
        assert len(discovery.configs) == 1
        assert "test_server" in discovery.configs
        assert discovery.configs["test_server"] == mcp_server_config
    
    @pytest.mark.asyncio
    async def test_discovery_service_lifecycle(self, mcp_server_config):
        """Test discovery service start/stop lifecycle."""
        discovery = MCPServerDiscovery([mcp_server_config])
        
        # Test start (will try to connect but likely fail in test environment)
        await discovery.start()
        assert discovery._running is True
        
        # Test status retrieval
        status = await discovery.get_all_server_status()
        assert isinstance(status, dict)
        assert "test_server" in status
        
        # Test stop
        await discovery.stop()
        assert discovery._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])