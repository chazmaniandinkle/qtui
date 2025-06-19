# Qwen-TUI Web UI Implementation Roadmap

*Last Updated: 2025-06-20 - Initial planning*

This document outlines the tasks required to provide a lightweight web interface for Qwen-TUI. The goal is to offer the same conversational agent experience in a browser as an alternative to the TUI.

## Phase 1: Basic Web Server & CLI Integration

1. **Add `webui` command** to `qwen-tui` CLI using Typer.
2. **Create a minimal FastAPI/Starlette server** that can start from the CLI command.
3. **Serve a simple HTML/JS frontend** with a chat input box and message display.

## Phase 2: Connect to the Agent System

1. Expose API endpoints for sending user prompts and streaming model responses.
2. Reuse existing backend/agent logic for completions and tool calls.
3. Implement WebSocket streaming so the browser receives tokens in real time.

## Phase 3: Achieve Feature Parity with TUI

1. Implement chat history management in the web session.
2. Provide model and backend selection options.
3. Mirror the permission prompts and tool output display.

## Phase 4: Testing & Documentation

1. Add automated tests for the new CLI command and web endpoints using `pytest` and HTTPX.
2. Document web UI usage and configuration in the main README.
3. Update release notes and examples to include the web UI option.

---

Once these phases are complete, users will be able to run `qwen-tui webui` to launch the browser-based interface alongside the existing TUI.
