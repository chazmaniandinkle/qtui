# Qwen-TUI: Comprehensive Implementation Guide

## Project Overview


*Status: Phase 2 Completed with full vLLM and OpenRouter support (2025-06-20)*

**Qwen-TUI** is a sophisticated terminal-based coding agent that combines Claude Code's proven UX patterns with Qwen3's powerful local inference capabilities. This guide provides a complete roadmap for implementing a production-ready system that works seamlessly across multiple LLM backends while maintaining the smooth developer experience that makes Claude Code exceptional.

## Implementation Strategy

### Phase-Based Development Approach

This implementation is structured in 4 distinct phases, each building upon the previous while maintaining a working system at every stage. Each phase is designed for optimal handoff to local coding agents like Claude Code.

---

## Phase 1: Foundation & Multi-Backend LLM System (Weeks 1-2)

### Phase 1.1: Project Structure & Dependencies (Days 1-2)

**Primary Task**: Create the foundational project structure with modern Python tooling.

```bash
# Target project structure
qwen-tui/
├── pyproject.toml          # Modern Python packaging
├── src/qwen_tui/
│   ├── __init__.py
│   ├── cli/                # Entry points and CLI
│   ├── backends/           # LLM backend implementations
│   ├── agents/             # Enhanced agent core
│   ├── tools/              # Tool implementations
│   ├── tui/                # Textual interface
│   └── utils/              # Shared utilities
├── tests/                  # Comprehensive test suite
├── docs/                   # Documentation
└── examples/               # Usage examples
```

**Specific Implementation Tasks**:

1. **Setup pyproject.toml** with:
   - Modern build system (hatchling/setuptools)
   - All required dependencies (textual, qwen-agent, pydantic, etc.)
   - Optional dependency groups for different backends
   - CLI entry points

2. **Create base configuration system**:
   - Use Pydantic for type-safe configuration
   - Support YAML/TOML config files
   - Environment variable overrides
   - Backend-specific configuration sections

3. **Initialize logging infrastructure**:
   - Structured logging with correlation IDs
   - Multiple output formats (JSON for debugging, human-readable for UI)
   - Backend-specific log channels

**Key Files to Create**:
- `src/qwen_tui/config.py` - Configuration models and loading
- `src/qwen_tui/logging.py` - Logging setup and utilities
- `src/qwen_tui/exceptions.py` - Custom exception hierarchy

### Phase 1.2: Backend Abstraction Layer (Days 3-5)

**Primary Task**: Implement the multi-backend LLM abstraction that supports vLLM, Ollama, LM Studio, and OpenRouter with automatic detection and failover.

**Core Backend Interface**:

```python
# src/qwen_tui/backends/base.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel

class LLMResponse(BaseModel):
    content: str
    tool_calls: Optional[List[Dict]] = None
    reasoning: Optional[str] = None
    usage: Optional[Dict] = None

class LLMBackend(ABC):
    @abstractmethod
    async def generate(
        self, 
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        stream: bool = True
    ) -> AsyncGenerator[LLMResponse, None]:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def backend_type(self) -> str:
        pass
```

**Implementation Order**:

1. **Base Backend Class** (`src/qwen_tui/backends/base.py`):
   - Abstract interface for all backends
   - Common functionality (retry logic, error handling)
   - Health check protocols

2. **Ollama Backend** (`src/qwen_tui/backends/ollama.py`):
   - Auto-detection of running Ollama service
   - Model discovery and validation
   - Streaming response handling

3. **LM Studio Backend** (`src/qwen_tui/backends/lm_studio.py`):
   - OpenAI-compatible API integration
   - Model hot-swap detection
   - GUI state synchronization

4. **vLLM Backend** (`src/qwen_tui/backends/vllm.py`):
   - Direct vLLM integration
   - Advanced parameter tuning
   - Performance optimization

5. **OpenRouter Backend** (`src/qwen_tui/backends/openrouter.py`):
   - API key management
   - Model selection and routing
   - Rate limiting and quotas

6. **Backend Manager** (`src/qwen_tui/backends/manager.py`):
   - Auto-discovery of available backends
   - Health monitoring and failover
   - User preference persistence

**Testing Strategy**:
- Mock backends for unit tests
- Integration tests with actual services
- Failover scenario testing

### Phase 1.3: Basic CLI and Backend Detection (Days 6-7)

**Primary Task**: Create the initial CLI interface with smart backend detection and setup workflows.

**CLI Structure**:

```bash
qwen-tui start                    # Auto-detect and start
qwen-tui backends list           # Show available backends
qwen-tui backends test           # Test all backends
qwen-tui setup vllm             # Guided vLLM setup
qwen-tui config show           # Show current configuration
```

**Implementation Tasks**:

1. **CLI Framework** (`src/qwen_tui/cli/main.py`):
   - Use Click or Typer for command structure
   - Rich console output for beautiful formatting
   - Progress indicators and status updates

2. **Backend Detection Logic** (`src/qwen_tui/cli/setup.py`):
   - Probe for existing Ollama/LM Studio installations
   - Guide users through initial configuration
   - Handle edge cases (no backends available, etc.)

3. **Configuration Wizard** (`src/qwen_tui/cli/wizard.py`):
   - Interactive setup for complex backends (vLLM)
   - Model recommendation engine
   - Performance tuning guidance

---

## Phase 2: Agent Core & TUI Framework (Weeks 3-4)

### Phase 2.1: Enhanced Qwen-Agent Integration (Days 1-3)

**Primary Task**: Extend Qwen-Agent with Claude Code-inspired patterns and multi-backend support.

**Core Agent Architecture**:

```python
# src/qwen_tui/agents/enhanced_assistant.py
from qwen_agent.agents import Assistant
from qwen_tui.backends.manager import BackendManager

class EnhancedAssistant(Assistant):
    def __init__(self, backend_manager: BackendManager, **kwargs):
        self.backend_manager = backend_manager
        super().__init__(**kwargs)
    
    async def plan_act_observe(self, user_input: str):
        # Implement Claude Code-style ReAct loop
        pass
```

**Implementation Tasks**:

1. **Context Management System** (`src/qwen_tui/agents/context.py`):
   - Project file indexing and summarization
   - Git status integration
   - Dynamic context updating during conversations
   - Token-efficient context compression per backend

2. **Tool Orchestrator** (`src/qwen_tui/agents/tools.py`):
   - Enhanced tool registry with MCP support
   - Permission gate integration
   - Streaming tool execution with real-time updates
   - Parallel tool execution capabilities

3. **ReAct Implementation** (`src/qwen_tui/agents/react.py`):
   - Plan → Act → Observe loop
   - Reasoning step visualization
   - Error recovery and replanning
   - Backend-optimized prompt formatting

### Phase 2.2: Textual TUI Framework (Days 4-6)

**Primary Task**: Build the core TUI interface using Textual with modern, responsive design.

**TUI Architecture**:

```python
# src/qwen_tui/tui/app.py
from textual.app import App
from textual.widgets import Header, Footer, Input, RichLog

class QwenTUIApp(App):
    CSS_PATH = "styles.css"
    
    def compose(self):
        yield Header()
        yield ChatPanel()
        yield StatusBar()
        yield Footer()
```

**Core Components**:

1. **Main Application** (`src/qwen_tui/tui/app.py`):
   - Application lifecycle management
   - Key binding system
   - Theme and styling support

2. **Chat Interface** (`src/qwen_tui/tui/chat.py`):
   - Message display with syntax highlighting
   - Streaming response visualization
   - Tool execution indicators
   - Copy/paste functionality

3. **Status System** (`src/qwen_tui/tui/status.py`):
   - Backend health monitoring
   - Performance metrics display
   - Real-time system status
   - Backend switching interface

4. **Input Handling** (`src/qwen_tui/tui/input.py`):
   - Multi-line input support
   - Command history and completion
   - File drag-and-drop handling
   - Keyboard shortcuts

### Phase 2.3: Basic Tool Implementation (Days 7)

**Primary Task**: Implement core tools required for basic coding assistance.

**Essential Tools**:

1. **File System Tools** (`src/qwen_tui/tools/filesystem.py`):
   - Enhanced file reading with syntax highlighting
   - Directory tree visualization
   - File search and filtering
   - Diff-based editing

2. **Shell Integration** (`src/qwen_tui/tools/shell.py`):
   - Persistent bash session
   - Command output streaming
   - Working directory management
   - Git command integration

3. **Project Analysis** (`src/qwen_tui/tools/project.py`):
   - Code structure analysis
   - Dependency mapping
   - Documentation scanning
   - Test discovery

---

## Phase 3: Advanced Features & Security (Weeks 5-6)

### Phase 3.1: Permission & Security System (Days 1-3)

**Primary Task**: Implement comprehensive security with risk assessment and user approval workflows.

**Security Architecture**:

```python
# src/qwen_tui/security/permissions.py
from enum import Enum
from typing import Dict, List

class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PermissionGate:
    async def assess_risk(self, tool_name: str, args: Dict) -> RiskLevel:
        # Implement risk assessment logic
        pass
    
    async def request_approval(self, action: str, risk: RiskLevel) -> bool:
        # Handle user approval workflow
        pass
```

**Implementation Tasks**:

1. **Risk Assessment Engine** (`src/qwen_tui/security/risk.py`):
   - Pattern-based dangerous command detection
   - File system access controls
   - Network operation monitoring
   - Data exfiltration prevention

2. **Permission UI** (`src/qwen_tui/tui/permissions.py`):
   - Modal approval dialogs
   - Risk level visualization
   - Action preview and explanation
   - Permanent approval options

3. **Security Policies** (`src/qwen_tui/security/policies.py`):
   - Configurable security profiles
   - Backend-specific security rules
   - Audit logging and compliance
   - Emergency stop mechanisms

### Phase 3.2: Performance Optimization (Days 4-5)

**Primary Task**: Optimize for different backend characteristics and implement advanced features.

**Optimization Areas**:

1. **Context Optimization** (`src/qwen_tui/agents/optimization.py`):
   - Backend-specific context compression
   - Intelligent context windowing
   - Semantic chunking for large projects
   - Dynamic context relevance scoring

2. **Parallel Execution** (`src/qwen_tui/agents/parallel.py`):
   - Sub-agent spawning with backend affinity
   - Concurrent tool execution
   - Result aggregation and merging
   - Resource management and throttling

3. **Caching System** (`src/qwen_tui/utils/cache.py`):
   - Response caching for repeated queries
   - Project analysis result caching
   - Backend-specific cache optimization
   - Cache invalidation strategies

### Phase 3.3: MCP Integration (Days 6-7)

**Primary Task**: Integrate MCP (Model Context Protocol) for extensible tool ecosystem.

**MCP Implementation**:

1. **MCP Client** (`src/qwen_tui/mcp/client.py`):
   - MCP server discovery and connection
   - Tool registration and schema validation
   - Resource management and lifecycle
   - Error handling and recovery

2. **Tool Proxy System** (`src/qwen_tui/mcp/proxy.py`):
   - Seamless integration with existing tool system
   - Permission gate integration for MCP tools
   - Performance monitoring and optimization
   - Security sandboxing for external tools

---

## Phase 4: Polish & Advanced Features (Weeks 7-8)

### Phase 4.1: Advanced TUI Features (Days 1-3)

**Primary Task**: Implement advanced UI features for power users.

**Advanced Features**:

1. **Backend Management UI** (`src/qwen_tui/tui/backends.py`):
   - Live backend switching
   - Performance comparison tools
   - Configuration management interface
   - Health monitoring dashboard

2. **Developer Tools** (`src/qwen_tui/tui/debug.py`):
   - Request/response inspection
   - Token usage analytics
   - Performance profiling
   - Debug log visualization

3. **Customization System** (`src/qwen_tui/tui/themes.py`):
   - Theme engine with CSS support
   - Custom keybinding configuration
   - Layout customization
   - Plugin system architecture

### Phase 4.2: Documentation & Examples (Days 4-5)

**Primary Task**: Create comprehensive documentation and example configurations.

**Documentation Structure**:

1. **User Documentation** (`docs/`):
   - Installation and setup guides
   - Backend configuration tutorials
   - Usage examples and workflows
   - Troubleshooting guides

2. **Developer Documentation** (`docs/dev/`):
   - Architecture overview
   - API reference
   - Plugin development guide
   - Contribution guidelines

3. **Example Configurations** (`examples/`):
   - Backend-specific configurations
   - Common workflow examples
   - MCP server integrations
   - Custom tool implementations

### Phase 4.3: Testing & Quality Assurance (Days 6-7)

**Primary Task**: Comprehensive testing and quality assurance.

**Testing Strategy**:

1. **Unit Tests** (`tests/unit/`):
   - Component isolation testing
   - Mock backend testing
   - Error condition validation
   - Edge case coverage

2. **Integration Tests** (`tests/integration/`):
   - Multi-backend testing
   - TUI interaction testing
   - MCP integration testing
   - End-to-end workflow validation

3. **Performance Tests** (`tests/performance/`):
   - Backend latency measurement
   - Memory usage profiling
   - Concurrent operation testing
   - Stress testing scenarios

---

## Implementation Guidelines for Claude Code

### Task Breakdown Strategy

Each phase is designed to maintain a working system while incrementally adding functionality. This approach is optimal for Claude Code because:

1. **Incremental Development**: Each task builds upon previous work
2. **Clear Dependencies**: Tasks are ordered to minimize blocking
3. **Testable Milestones**: Each phase produces demonstrable functionality
4. **Modular Architecture**: Components can be developed independently

### File Organization Principles

- **Single Responsibility**: Each file has a clear, focused purpose
- **Import Hygiene**: Minimal dependencies between modules
- **Test Co-location**: Tests mirror source structure
- **Documentation Integration**: Docstrings and type hints throughout

### Implementation Priorities

**Phase 1 Priority**: Get basic multi-backend system working
- Focus on Ollama backend first (easiest to set up)
- Implement basic CLI for testing
- Ensure backend switching works reliably

**Phase 2 Priority**: Create functional TUI with basic agent
- Textual interface with chat functionality
- Basic tool integration (file ops, shell)
- ReAct loop implementation

**Phase 3 Priority**: Security and advanced features
- Permission system for safe operation
- Performance optimizations
- MCP integration for extensibility

**Phase 4 Priority**: Polish and production readiness
- Advanced UI features
- Comprehensive documentation
- Testing and quality assurance

### Code Quality Standards

1. **Type Safety**: Use Pydantic models and type hints throughout
2. **Error Handling**: Comprehensive exception handling with user-friendly messages
3. **Async/Await**: Proper async patterns for all I/O operations
4. **Configuration**: Everything configurable through files or environment
5. **Logging**: Structured logging with appropriate levels
6. **Documentation**: Clear docstrings and inline comments

### Testing Approach

- **Mock Early**: Create mock backends for rapid development
- **Test-Driven**: Write tests alongside implementation
- **Integration Focus**: Emphasize integration tests for complex interactions
- **Performance Baseline**: Establish performance benchmarks early

### Success Criteria

**Phase 1 Complete**: Can start Qwen-TUI and have it auto-detect and connect to available backends
**Phase 2 Complete**: Can have a basic conversation with file operations through TUI
**Phase 3 Complete**: System is secure and performs well with advanced features
**Phase 4 Complete**: Production-ready system with comprehensive documentation

---

## Quick Start Commands for Claude Code

```bash
# Initialize the project
mkdir qwen-tui && cd qwen-tui
git init

# Start with Phase 1.1: Project Structure
# Create pyproject.toml with modern Python packaging
# Set up src/qwen_tui/ directory structure
# Initialize configuration and logging systems

# Phase 1.2: Backend Implementation
# Implement base backend interface
# Add Ollama backend (start here - easiest)
# Create backend manager with auto-detection

# Phase 1.3: Basic CLI
# Add Click-based CLI with rich output
# Implement backend detection and setup
# Create configuration wizard

# Continue through phases sequentially...
```

This implementation guide provides a complete roadmap for building Qwen-TUI from scratch, with each task specifically designed for efficient implementation by local coding agents like Claude Code. The modular, phase-based approach ensures steady progress while maintaining a working system at every stage.
