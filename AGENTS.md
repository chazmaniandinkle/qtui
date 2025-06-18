# AGENTS.md

## Qwen-TUI Test Scripts and Agent Resources

This document describes all test scripts available in the `tests/` directory. These scripts are useful for developers, agents, and anyone maintaining or extending Qwen-TUI.

---

## Automated Tests (run with pytest or similar)

| Script                  | Purpose                                 | How to Run                  |
|-------------------------|-----------------------------------------|-----------------------------|
| test_backends.py        | Unit tests for backend logic            | `pytest tests/test_backends.py` |
| test_config.py          | Unit tests for configuration            | `pytest tests/test_config.py`   |
| test_history.py         | Unit tests for conversation history     | `pytest tests/test_history.py`  |
| test_tui.py             | Unit tests for TUI core logic           | `pytest tests/test_tui.py`      |

---

## Manual / Agent-Use / Integration Test Scripts

| Script                        | Purpose                                              | How to Run                                 | Notes                |
|-------------------------------|------------------------------------------------------|--------------------------------------------|----------------------|
| test_simple_thinking.py       | Headless/unit test for Thinking/ActionWidget         | `python tests/test_simple_thinking.py`     | No UI, quick checks  |
| test_full_thinking_fixed.py   | Manual integration test of thinking UI               | `python tests/test_full_thinking_fixed.py` | Textual UI           |
| test_full_thinking_system.py  | End-to-end test of thinking system                   | `python tests/test_full_thinking_system.py`| Textual UI, backend  |
| test_thinking_widgets.py      | Manual UI test for widgets                           | `python tests/test_thinking_widgets.py`    | Textual UI           |
| test_tui_layout.py            | Layout and stress test for TUI                       | `python tests/test_tui_layout.py`          | Textual UI           |

---

## Usage Notes

- **Automated tests** can be run with `pytest` or your preferred test runner.
- **Manual/agent-use scripts** are not run automatically by CI, but are available for agents and developers to use as needed. Run them with `python <script_path>`.
- Scripts with a Textual UI require a terminal that supports Textual.
- These scripts are valuable for debugging, regression testing, and agent-driven workflows.

---

For more information, see the main `README.md` or contact the maintainers.
