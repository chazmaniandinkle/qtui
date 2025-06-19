# MCP Integration Guide

This guide explains how to configure and use Model Context Protocol (MCP) integration with Qwen-TUI.

## Overview

MCP (Model Context Protocol) allows Qwen-TUI to connect to remote tool servers, extending the built-in tool capabilities with specialized tools from the community or custom implementations.

### Benefits

- **Extended Tool Ecosystem**: Access to web search, specialized APIs, database tools, and more
- **Community Tools**: Use tools developed by the community
- **Custom Extensions**: Build your own MCP servers for specific workflows
- **Seamless Integration**: MCP tools work identically to local tools
- **Security**: Full integration with Qwen-TUI's permission system

## Quick Start

### 1. Enable MCP in Configuration

Add MCP configuration to your `config.yaml`:

```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      url: "ws://localhost:3001"
      enabled: true
```

### 2. Start MCP Servers

Run your MCP servers (examples):

```bash
# Example filesystem server
npx @modelcontextprotocol/server-filesystem ws://localhost:3001

# Example web tools server
npx @modelcontextprotocol/server-web ws://localhost:3002
```

### 3. Use MCP Tools

MCP tools appear alongside local tools and can be used by agents:

```
User: Search for information about MCP protocol
Agent: I'll use the web search tool to find information about MCP.
[Uses mcp_web_tools_search_web tool]
```

## Configuration

### Basic Configuration

```yaml
mcp:
  enabled: true
  auto_discover: true
  tool_prefix: true
  servers:
    - name: "server_name"
      url: "ws://localhost:3001"
      enabled: true
```

### Advanced Configuration

```yaml
mcp:
  enabled: true
  auto_discover: true
  tool_prefix: true
  max_concurrent_calls: 5
  connection_timeout: 10

  servers:
    - name: "filesystem"
      url: "ws://localhost:3001"
      enabled: true
      timeout: 30
      tools: ["read_file", "write_file"]  # Specific tools only
      retry_attempts: 3
      retry_delay: 1.0
      health_check_interval: 60

    - name: "web_tools"
      url: "wss://secure-server.com/ws"
      enabled: true
      timeout: 60
      auth:
        Authorization: "Bearer your-api-key"
        X-Custom-Header: "value"
```

### Environment Variables

Set MCP configuration via environment variables:

```bash
export QWEN_TUI_MCP_ENABLED=true
export QWEN_TUI_MCP_SERVERS="ws://localhost:3001,ws://localhost:3002"
```

## MCP Server Examples

### Popular MCP Servers

1. **Filesystem Server**
   ```bash
   npm install @modelcontextprotocol/server-filesystem
   npx @modelcontextprotocol/server-filesystem ws://localhost:3001
   ```

2. **Web Tools Server**
   ```bash
   npm install @modelcontextprotocol/server-web
   npx @modelcontextprotocol/server-web ws://localhost:3002
   ```

3. **Database Server**
   ```bash
   npm install @modelcontextprotocol/server-database
   npx @modelcontextprotocol/server-database ws://localhost:3003
   ```

### Custom MCP Server

Create a simple MCP server:

```javascript
// simple-mcp-server.js
const { MCPServer } = require('@modelcontextprotocol/sdk');

const server = new MCPServer({
  name: "custom-tools",
  version: "1.0.0"
});

server.addTool({
  name: "echo",
  description: "Echo back the input",
  parameters: {
    type: "object",
    properties: {
      text: { type: "string", description: "Text to echo" }
    },
    required: ["text"]
  },
  handler: async (params) => {
    return {
      content: [{ type: "text", text: `Echo: ${params.text}` }]
    };
  }
});

server.listen(3004);
```

## Tool Discovery and Usage

### Automatic Discovery

When MCP is enabled, Qwen-TUI automatically:
1. Connects to configured servers
2. Discovers available tools
3. Registers tools with the tool registry
4. Makes tools available to agents

### Tool Naming

MCP tools are named with the pattern: `mcp_{server_name}_{tool_name}`

Example: `mcp_filesystem_read_file`, `mcp_web_tools_search`

### Tool Information

Get information about available tools:

```python
from qwen_tui.tools import get_tool_manager

manager = get_tool_manager()
await manager.initialize_mcp()

# List all tools (local + MCP)
tools = manager.registry.list_tools()

# Get MCP-specific information
mcp_tools = manager.registry.get_tools_by_type()
print(f"Local tools: {mcp_tools['local']}")
print(f"MCP tools: {mcp_tools['mcp']}")

# Get detailed tool info
tool_info = manager.registry.get_tool_info("mcp_filesystem_read_file")
```

## Security and Permissions

### Permission Integration

MCP tools integrate with Qwen-TUI's permission system:

- All MCP tool calls go through permission checking
- Risk assessment applies to MCP tools
- User approval required for risky operations
- YOLO mode works with MCP tools

### Security Configuration

Configure security for MCP tools:

```yaml
security:
  profile: "balanced"
  require_approval_for:
    - "mcp_tool_call"      # Require approval for all MCP tools
    - "network_request"    # Require approval for network operations
  blocked_commands:
    - "mcp_*_delete_*"     # Block any MCP delete operations
```

### Risk Assessment

MCP tools are assessed for risk based on:
- Tool name patterns (delete, remove, etc.)
- Parameter content (file paths, URLs, etc.)
- Server reputation and configuration
- User-defined risk rules

## Monitoring and Debugging

### Server Status

Check MCP server status:

```python
from qwen_tui.mcp import get_integration_manager

manager = get_integration_manager()
status = await manager.get_server_status()

for server_name, info in status.items():
    print(f"Server {server_name}: {info['status']}")
    print(f"Tools: {info['tools']}")
```

### Health Monitoring

Qwen-TUI automatically monitors MCP server health:
- Periodic ping checks
- Automatic reconnection on failure
- Graceful degradation when servers unavailable
- Health status in UI panels

### Debugging

Enable debug logging for MCP:

```yaml
logging:
  level: "DEBUG"

# Or via environment
export QWEN_TUI_LOG_LEVEL=DEBUG
```

Debug information includes:
- Connection attempts and failures
- Tool discovery and registration
- Tool execution and results
- Error messages and stack traces

## Performance Optimization

### Connection Pooling

MCP clients use connection pooling for efficiency:
- Persistent WebSocket connections
- Automatic reconnection
- Connection reuse across tool calls

### Caching

Tool results can be cached:
- Configurable cache duration
- LRU eviction policy
- Per-tool cache settings

### Concurrent Execution

Control concurrent MCP tool calls:

```yaml
mcp:
  max_concurrent_calls: 5  # Limit concurrent calls
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   ```
   Error: Failed to connect to MCP server
   ```
   - Check server is running
   - Verify URL and port
   - Check firewall settings

2. **Tools Not Appearing**
   ```
   No MCP tools available
   ```
   - Verify MCP is enabled in config
   - Check server connection status
   - Review server tool implementation

3. **Permission Denied**
   ```
   Permission denied for MCP tool
   ```
   - Review security configuration
   - Check permission requirements
   - Verify user approval settings

### Debug Commands

Useful debug commands:

```bash
# Test MCP server connection
curl -H "Upgrade: websocket" ws://localhost:3001

# Check Qwen-TUI logs
tail -f ~/.local/share/qwen-tui/logs/qwen-tui.log

# Test tool execution
python -c "
from qwen_tui.mcp.integration import test_mcp_integration
import asyncio
asyncio.run(test_mcp_integration())
"
```

## Best Practices

### Server Configuration

1. **Use specific tool lists** for better control
2. **Set appropriate timeouts** for your use case
3. **Configure retry settings** for reliability
4. **Use authentication** for secure servers

### Security

1. **Review MCP tools** before enabling servers
2. **Use permission system** to control access
3. **Monitor tool usage** for suspicious activity
4. **Keep servers updated** for security patches

### Performance

1. **Limit concurrent calls** to prevent overload
2. **Use local tools** for frequently used operations
3. **Cache results** when appropriate
4. **Monitor server performance** and response times

## Example Workflows

### Development Workflow

```yaml
# Development-focused MCP configuration
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      url: "ws://localhost:3001"
      tools: ["read_file", "write_file", "search_files"]

    - name: "git_tools"
      url: "ws://localhost:3002"
      tools: ["git_status", "git_diff", "git_commit"]

    - name: "docker_tools"
      url: "ws://localhost:3003"
      tools: ["docker_ps", "docker_logs", "docker_exec"]
```

### Research Workflow

```yaml
# Research-focused MCP configuration
mcp:
  enabled: true
  servers:
    - name: "web_search"
      url: "ws://localhost:3001"
      tools: ["search_web", "fetch_url", "summarize_page"]

    - name: "academic_tools"
      url: "ws://localhost:3002"
      tools: ["search_papers", "fetch_arxiv", "cite_paper"]

    - name: "data_tools"
      url: "ws://localhost:3003"
      tools: ["analyze_csv", "plot_data", "statistics"]
```

## Community Resources

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Official MCP Servers](https://github.com/modelcontextprotocol/servers)
- [Community MCP Registry](https://mcp-registry.io/)
- [Qwen-TUI MCP Examples](https://github.com/qwen-tui/mcp-examples)

## Contributing

To contribute MCP servers or improvements:

1. Review the [MCP specification](https://spec.modelcontextprotocol.io/)
2. Create servers following best practices
3. Submit to community registry
4. Share examples and tutorials

## Support

For MCP-related issues:

1. Check this documentation
2. Review server logs and Qwen-TUI logs
3. Test with minimal configuration
4. Report issues with detailed logs and configuration
