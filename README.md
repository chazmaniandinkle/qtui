# Qwen-TUI

A sophisticated terminal-based coding agent that combines Claude Code's proven UX patterns with Qwen3's powerful local inference capabilities.

## Overview

Qwen-TUI provides a production-ready terminal interface for AI-powered coding assistance, featuring:

- **Multi-Backend Support**: Seamlessly switch between Ollama, LM Studio, vLLM, and OpenRouter
- **Claude Code-Inspired UX**: Familiar interface patterns for developers
- **Advanced Security**: Risk assessment and permission gates for safe operation
- **High Performance**: Optimized for local inference with efficient context management
- **Extensible Architecture**: MCP integration for unlimited tool expansion
- **Hybrid Tool Ecosystem**: Local tools + remote MCP servers for maximum capabilities

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/qwen-tui.git
cd qwen-tui

# Install with pip (recommended)
pip install -e .

# Or install with optional dependencies
pip install -e ".[ollama,lm-studio,all]"
```

### Basic Usage

```bash
# Auto-detect and start with available backends
qwen-tui start

# List available backends
qwen-tui backends list

# Test all backends
qwen-tui backends test

# Show current configuration
qwen-tui config show

# Enable verbose debug logging
qwen-tui --debug start
```

### Slash Commands

Inside the TUI you can use several helpful commands:

```
/help      Show keyboard shortcuts and command list
/clear     Start a new conversation and clear history
/history   List recent conversation sessions
/load ID   Load a previous session by ID
/export fmt  Export the current session (json or txt)
```

## Features

### Multi-Backend Architecture

Qwen-TUI automatically detects and connects to available LLM backends:

- **Ollama**: Local models with automatic discovery
- **LM Studio**: Desktop GUI integration with hot-swap support
- **vLLM**: High-performance inference server
- **OpenRouter**: Cloud-based model access

### Security & Permissions

Built-in security features ensure safe operation:

- Risk assessment for all operations
- Configurable permission profiles
- User approval workflows for sensitive actions
- Audit logging and compliance tracking

### Performance Optimization

Optimized for efficient local inference:

- Backend-specific context compression
- Intelligent context windowing
- Parallel tool execution
- Response caching and optimization

## Configuration

### Basic Configuration

Create a `config.yaml` file in your project directory or `~/.config/qwen-tui/`:

```yaml
# Backend preferences (in order of preference)
preferred_backends:
  - ollama
  - lm_studio

# Ollama configuration
ollama:
  host: localhost
  port: 11434
  model: "qwen2.5-coder:latest"

# Security settings
security:
  profile: balanced
  allow_file_write: true
  allow_file_delete: false

# UI preferences
ui:
  theme: dark
  show_typing_indicator: true
```

### Environment Variables

Override configuration with environment variables:

```bash
export QWEN_TUI_BACKENDS=ollama,lm_studio
export QWEN_TUI_OLLAMA_MODEL=qwen2.5-coder:7b
export QWEN_TUI_LOG_LEVEL=DEBUG
```


### Additional Backend Configuration

For vLLM and OpenRouter, specify connection details in `config.yaml` or via environment variables.

```yaml
vllm:
  host: localhost
  port: 8000
  model: Qwen/Qwen2.5-Coder-7B-Instruct
openrouter:
  api_key: YOUR_API_KEY
  model: deepseek/deepseek-r1-0528-qwen3-8b
```

Set via environment variables if preferred:

```bash
export QWEN_TUI_VLLM_HOST=localhost
export QWEN_TUI_VLLM_PORT=8000
export QWEN_TUI_OPENROUTER_MODEL=deepseek/deepseek-r1-0528-qwen3-8b
export OPENROUTER_API_KEY=<key>
```

## MCP Integration

Qwen-TUI supports **Model Context Protocol (MCP)** for extending tool capabilities with remote servers.

### Quick Start with MCP

1. **Enable MCP in your config:**
```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      url: "ws://localhost:3001"
      enabled: true
```

2. **Start an MCP server:**
```bash
# Example: Filesystem tools server
npx @modelcontextprotocol/server-filesystem ws://localhost:3001
```

3. **Use MCP tools in conversations:**
```
User: Search for files containing "config" in the current directory
Agent: I'll use the filesystem tools to search for files.
[Uses mcp_filesystem_search_files tool]
```

### MCP Features

- **Seamless Integration**: MCP tools work identically to built-in tools
- **Auto-Discovery**: Automatic tool registration from MCP servers
- **Health Monitoring**: Automatic reconnection and error recovery
- **Security Integration**: Full permission system compatibility
- **Performance Optimized**: Connection pooling and concurrent execution

### Popular MCP Servers

- **Filesystem Tools**: File operations and search
- **Web Tools**: Web search and URL fetching
- **Database Tools**: SQL queries and schema inspection
- **Git Tools**: Version control operations
- **Custom Tools**: Build your own MCP servers

For complete MCP documentation, see [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md).

## Development

### Project Structure

```
qwen-tui/
├── src/qwen_tui/           # Main package
│   ├── cli/                # CLI interface
│   ├── backends/           # LLM backend implementations
│   ├── agents/             # Agent core and ReAct loop
│   ├── tools/              # Tool implementations
│   ├── mcp/                # MCP integration (NEW)
│   ├── tui/                # Textual UI components
│   └── utils/              # Shared utilities
├── tests/                  # Test suite
├── docs/                   # Documentation
└── examples/               # Usage examples
```

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run type checking
mypy src/qwen_tui

# Format code
black src/ tests/
isort src/ tests/
```

### Backend Development

To add a new backend, implement the `LLMBackend` interface:

```python
from qwen_tui.backends.base import LLMBackend, LLMResponse

class MyBackend(LLMBackend):
    async def generate(self, messages, tools=None, stream=True):
        # Implementation here
        pass

    async def health_check(self):
        # Health check implementation
        pass

    @property
    def backend_type(self):
        return "my_backend"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Run linting (`black`, `isort`, `mypy`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by [Claude Code](https://claude.ai/code) for UX patterns
- Built on [Qwen](https://github.com/QwenLM/Qwen) for local inference
- Uses [Textual](https://textual.textualize.io/) for the terminal interface
- Powered by [Pydantic](https://pydantic.dev/) for configuration management

## Support

- 📖 [Documentation](docs/README.md)
- 🐛 [Issues](https://github.com/your-org/qwen-tui/issues)
- 💬 [Discussions](https://github.com/your-org/qwen-tui/discussions)

---

*Qwen-TUI: Bringing the power of local AI inference to your terminal with the UX you love.*
