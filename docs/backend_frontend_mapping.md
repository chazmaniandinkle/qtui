# Backend ↔ Frontend Mapping

This document maps backend functions and tools to the frontend (TUI) and internal agent system.

## Overview
Qwen‑TUI uses a layered architecture:

1. **Backends** (`src/qwen_tui/backends/`)
2. **BackendManager** (`src/qwen_tui/backends/manager.py`)
3. **Tools & ToolManager** (`src/qwen_tui/tools/`)
4. **Agents** (`src/qwen_tui/agents/`)
5. **ThinkingManager** & **TUI** (`src/qwen_tui/tui/`)

The frontend TUI interacts with the ThinkingManager which drives a ReAct agent. The agent relies on the BackendManager for LLM completions and on the ToolManager for executing tools. The permission system mediates tool usage.

## Backends
| Module | Key Functions | Used By |
| --- | --- | --- |
| `ollama.py` | `initialize`, `generate`, `health_check`, `get_available_models`, `pull_model`, `delete_model` | BackendManager, indirectly agents/TUI |
| `lm_studio.py` | `initialize`, `generate`, `health_check`, `get_detailed_models`, `switch_model` | BackendManager |
| `vllm.py` | `initialize`, `generate`, `health_check`, `get_available_models` | BackendManager |
| `openrouter.py` | `initialize`, `generate`, `health_check`, `get_detailed_models` | BackendManager |

Backends implement the `LLMBackend` interface defined in `base.py` which includes methods like `generate` and `health_check`【F:src/qwen_tui/backends/base.py†L55-L122】.

## BackendManager
`BackendManager` discovers and coordinates backends. It exposes:
- `initialize` and `discover_backends` to set up connections.
- `generate` to route requests to the preferred backend with fallback logic.
- Model management helpers (`get_all_models`, `switch_model`, etc.)【F:src/qwen_tui/backends/manager.py†L1-L217】【F:src/qwen_tui/backends/manager.py†L217-L353】.

The manager is used by both the ThinkingManager and the TUI application to request completions and fetch backend status.

## Tools and ToolManager
Tools reside in `src/qwen_tui/tools/` and are registered via `ToolRegistry`【F:src/qwen_tui/tools/registry.py†L8-L64】. Key tools include:
- File tools: `ReadTool`, `WriteTool`, `EditTool`, `MultiEditTool`【F:src/qwen_tui/tools/file_tools.py†L12-L140】【F:src/qwen_tui/tools/file_tools.py†L140-L209】.
- Search tools: `GrepTool`, `GlobTool`, `LSTool`【F:src/qwen_tui/tools/search_tools.py†L8-L80】【F:src/qwen_tui/tools/search_tools.py†L160-L247】.
- Execution tools: `BashTool`, `TaskTool`, `NotebookTool`【F:src/qwen_tui/tools/execution_tools.py†L13-L64】【F:src/qwen_tui/tools/execution_tools.py†L160-L253】.

`ToolManager` executes tools and keeps history【F:src/qwen_tui/tools/registry.py†L118-L188】. Tools are exposed to the agent via OpenAI‑style schemas.

## Agents
Agents defined in `src/qwen_tui/agents/` use the ToolManager and BackendManager. `ReActAgent` implements a Plan‑Act‑Observe loop, extracting tool calls from model responses and executing them【F:src/qwen_tui/agents/react.py†L1-L75】【F:src/qwen_tui/agents/react.py†L156-L231】.

The base agent provides the system prompt and handles conversation history【F:src/qwen_tui/agents/base.py†L1-L157】【F:src/qwen_tui/agents/base.py†L160-L219】.

## ThinkingManager and TUI
`ThinkingManager` connects the UI with the agents, creating `ReActAgent` instances and streaming updates to the interface【F:src/qwen_tui/tui/thinking.py†L1-L63】【F:src/qwen_tui/tui/thinking.py†L120-L177】. The TUI app (`app.py`) initializes `BackendManager`, `ThinkingManager`, and a `TUIPermissionManager` to handle user permissions before tools run【F:src/qwen_tui/tui/app.py†L1-L60】【F:src/qwen_tui/tui/app.py†L88-L120】.

The TUI listens for user input and forwards conversation history to the ThinkingManager, which in turn uses the agent to interact with backends and execute tools. Tool execution progress is displayed via widgets (`ThinkingWidget`, `ActionWidget`).

## Permission System
Tool executions are filtered through the permission manager. `TUIPermissionManager` wraps the core `PermissionManager` and prompts the user when a tool is high‑risk【F:src/qwen_tui/tui/permission_manager.py†L1-L76】【F:src/qwen_tui/tui/permission_manager.py†L77-L148】.

## Flow Summary
1. **User input** is captured by the TUI.
2. The TUI calls **ThinkingManager.think_and_respond** which invokes a **ReActAgent**.
3. The agent uses **BackendManager.generate** to get LLM output and extracts tool calls.
4. Tool calls are executed via **ToolManager** after permission checks.
5. Results and agent messages stream back through the ThinkingManager to the TUI.

This mapping shows how backend functions and tools propagate through the agent system to the frontend.
