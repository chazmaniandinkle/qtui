"""Simple in-memory chat panel for unit tests."""
from __future__ import annotations

from typing import List, Tuple


class ChatPanel:
    """Lightweight chat panel used for testing."""

    def __init__(self) -> None:
        self.messages: List[Tuple[str, str]] = []
        self.typing_indicator_visible: bool = False

    def add_user_message(self, content: str) -> None:
        self.messages.append(("user", content))

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(("assistant", content))

    def add_system_message(self, content: str) -> None:
        self.messages.append(("system", content))

    def add_error_message(self, content: str) -> None:
        self.messages.append(("error", content))

    def update_assistant_message(self, content: str) -> None:
        if self.messages and self.messages[-1][0] == "assistant":
            self.messages[-1] = ("assistant", content)
        else:
            self.add_assistant_message(content)

    def show_typing_indicator(self) -> None:
        self.typing_indicator_visible = True

    def hide_typing_indicator(self) -> None:
        self.typing_indicator_visible = False

    def clear_messages(self) -> None:
        self.messages.clear()
        self.typing_indicator_visible = False

    # Methods used in performance tests
    def refresh_display(self) -> None:  # pragma: no cover
        """Placeholder for compatibility with old UI tests."""
        pass

