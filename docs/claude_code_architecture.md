# Claude Code Agent Architecture

This document contains the comprehensive architecture breakdown of Claude Code, providing insights for implementing similar capabilities in Qwen-TUI.

## Core Architecture Pattern

Claude Code follows a **REPL-based agent architecture** with a **Plan → Act → Observe** loop that uses the **ReAct paradigm** (Reason and Act). The system operates as a local CLI-based AI coding assistant with several interacting subsystems.

## Key Architectural Components

### 1. CLI Interface & Terminal I/O
- Manages user input/output in terminal with a continuous loop
- Handles special slash commands (`/help`, `/clear`, `/commit`, etc.)
- Displays tool activities with visual indicators (`⏺` for tool use, `⎿` for completion)
- Captures key events (Escape to edit, Ctrl+C to interrupt)
- Uses monospace formatting appropriate for CLI
- Cleans up stale conversation logs automatically

### 2. AI Integration (Reasoning Engine)
- **Dual-model strategy**: Uses Claude 3.7 Sonnet for complex reasoning, Claude 3.5 Haiku for lightweight tasks
- Maintains system prompt with tool descriptions and safety rules
- Uses scratchpad contexts for internal reasoning (hidden from user)
- Supports "ultrathink" mode for complex reasoning with more model budget

### 3. Tool Registry & Execution System
- **Built-in tools**: File operations, search (Glob/Grep), shell execution, Git operations
- **External tools**: MCP (Model Context Protocol) integration for extending capabilities
- **BatchTool**: Parallel tool execution for performance
- **Sub-agent spawning**: Task/dispatch_agent tool for parallel processing

### 4. Context Management
- **Static context injection**: Directory structure, Git status at session start
- **Persistent state**: Bash shell maintains working directory and environment
- **Thread management**: `/clear` resets context, `/compact` summarizes history
- **File indexing**: Fast search across large codebases

### 5. Security & Permission System
- **Command classification**: Risk assessment for shell commands
- **User confirmation**: Prompts for potentially destructive operations
- **"YOLO mode"**: `--dangerously-skip-permissions` to bypass safety
- **Output sanitization**: Truncates large outputs, escapes special markers

## Key Design Principles

### 1. Modular Architecture
```
├── CLI Interface & Terminal I/O
├── Configuration Management
├── Codebase Context & Analysis
├── Command Parsing & Execution
├── AI Integration (Reasoning Engine)
├── Tools & Plugins Interface
├── File Operations
├── Shell Execution Sandbox
├── Authentication & API Integration
├── Telemetry and Logging
├── Error Handling
└── Utilities
```

### 2. ReAct Agent Pattern
- **System prompt**: Explicitly lists available tools with descriptions
- **Tool invocation**: Model outputs structured tool calls
- **Result integration**: Tool outputs fed back into model context
- **Iterative refinement**: Continues until task completion

### 3. Context Assembly Strategy
```
Prompt = System Instructions + Context Blocks + Conversation History + User Query
```
- Context blocks use special tokens: `<context name="directoryStructure">...</context>`
- Static snapshots taken at session start (not dynamically updated)
- Model warned about static nature of context

### 4. Tool Execution Flow
1. **Parse tool request** from model output
2. **Route to appropriate handler** (internal vs MCP)
3. **Execute with safety checks** and user confirmation if needed
4. **Capture and post-process output** (truncation, sanitization)
5. **Feed result back to model** for next iteration

## MCP Integration Architecture

### Client-Server Model
- Claude Code acts as **MCP client** consuming external tool servers
- Can also act as **MCP server** exposing its tools to other clients
- Configuration via `.mcp.json` files (project or global scope)

### Tool Integration Types
- **HTTP-based servers**: REST/JSON communication
- **Process-based servers**: STDIO communication with persistent subprocesses
- **Schema validation**: Uses Zod library for input/output validation

## Performance Optimizations

### 1. Parallel Processing
- BatchTool for concurrent tool execution
- Sub-agent spawning for non-blocking searches
- Persistent shell sessions to avoid startup costs

### 2. Dual-Model Strategy
- Fast model for classification/summarization
- Powerful model for main coding tasks
- Balances speed and cost

### 3. Context Optimization
- File indexing for fast searches
- Output truncation to stay within token limits
- Context compaction to manage memory

## Key Implementation Insights for Qwen-TUI

1. **Adopt the Plan-Act-Observe loop** with clear visual indicators
2. **Implement a robust tool registry** with schema validation
3. **Use dual-model approach** for performance optimization
4. **Build comprehensive permission system** with risk assessment
5. **Maintain persistent state** (shell sessions, context)
6. **Support MCP protocol** for extensibility
7. **Implement context assembly** with static snapshots
8. **Add sub-agent capabilities** for parallel processing
9. **Build proper error handling** with user-friendly messages
10. **Support thread management** with clear/compact operations

The architecture emphasizes **modularity**, **security**, **performance**, and **extensibility** while maintaining a clean user experience through the terminal interface.

## Visual Indicators

Claude Code uses specific visual indicators for different types of operations:
- `⏺` Tool execution in progress
- `⎿` Tool completion
- `🤔` Thinking/reasoning phase
- `✅` Successful completion
- `❌` Error or failure
- `⚠️` Warning or caution needed

## Implementation Priority

Based on Claude Code's architecture, the highest priority components for Qwen-TUI are:

1. **ReAct agent loop** - Core reasoning pattern
2. **Tool registry** - Extensible tool system
3. **Context assembly** - Proper prompt construction
4. **Permission system** - Security and safety
5. **Visual indicators** - Clear user feedback
6. **Persistent state** - Shell and context management
7. **Error handling** - Robust failure recovery
8. **MCP integration** - Future extensibility