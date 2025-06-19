from __future__ import annotations

from typing import Optional

from textual.events import Click
from textual.timer import Timer
from textual.widgets import Static


class ChatMessage(Static):
    def __init__(self, role: str, content: str = ""):
        super().__init__(content)
        self.role = role
        self.update_content(content)

    def update_content(self, content: str) -> None:
        if self.role == "user":
            self.update(f"[bold blue]You:[/bold blue] {content}")
        elif self.role == "assistant":
            self.update(f"[bold green]Assistant:[/bold green] {content}")
        elif self.role == "system":
            self.update(f"[dim italic]{content}[/dim italic]")
        elif self.role == "error":
            self.update(f"[bold red]Error:[/bold red] {content}")
        else:
            self.update(content)


class ThinkingWidget(Static):
    """Widget that displays thinking animation and preview text."""

    def __init__(self, thinking_text: str = ""):
        super().__init__()
        self.thinking_text = thinking_text
        self.full_thoughts = ""
        self.is_expanded = False
        self.spinner_frame = 0
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.timer: Optional[Timer] = None
        self.add_class("thinking-widget")
        self.update_display()

    def start_thinking(self) -> None:
        if self.timer is None:
            self.timer = self.set_interval(0.5, self.update_spinner)

    def stop_thinking(self) -> None:
        if self.timer:
            self.timer.stop()
            self.timer = None

    def update_spinner(self) -> None:
        self.spinner_frame = (self.spinner_frame + 1) % len(self.spinner_chars)
        self.update_display()

    def update_thinking_text(self, text: str) -> None:
        self.thinking_text = text
        if len(text) > 80:
            self.thinking_text = text[:77] + "..."
        self.update_display()

    def set_full_thoughts(self, thoughts: str) -> None:
        self.full_thoughts = thoughts

    def update_display(self) -> None:
        if self.is_expanded:
            content = f"🤔 Thinking (expanded):\n{self.full_thoughts}"
        else:
            spinner = self.spinner_chars[self.spinner_frame] if self.timer else "💭"
            preview = self.thinking_text if self.thinking_text else "Thinking..."
            content = f"{spinner} {preview}"
        self.update(content)

    def toggle_expansion(self) -> None:
        self.is_expanded = not self.is_expanded
        self.update_display()

    def on_click(self, event: Click) -> None:
        if self.full_thoughts:
            self.toggle_expansion()
            event.stop()


class ActionWidget(Static):
    """Widget that displays individual tool action results."""

    def __init__(self, action_type: str, tool_name: str, status: str = "running"):
        super().__init__()
        self.action_type = action_type
        self.tool_name = tool_name
        self.status = status
        self.parameters: dict[str, str] = {}
        self.result = ""
        self.error = ""
        self.add_class("action-widget")
        self.update_display()

    def set_parameters(self, params: dict) -> None:
        self.parameters = params
        self.update_display()

    def set_result(self, result: str) -> None:
        self.result = result
        self.status = "completed"
        self.update_display()

    def set_error(self, error: str) -> None:
        self.error = error
        self.status = "error"
        self.update_display()

    def update_display(self) -> None:
        if self.status == "running":
            icon = "🔄"
            status_text = f"Running {self.tool_name}..."
        elif self.status == "completed":
            icon = "✅"
            status_text = f"Completed {self.tool_name}"
        elif self.status == "error":
            icon = "❌"
            status_text = f"Failed {self.tool_name}"
        else:
            icon = "⚪"
            status_text = f"{self.tool_name}"

        content = f"{icon} {status_text}"
        if self.parameters:
            params_str = ", ".join([f"{k}={v}" for k, v in list(self.parameters.items())[:2]])
            if len(self.parameters) > 2:
                params_str += "..."
            content += f"\n  Parameters: {params_str}"
        if self.result:
            result_preview = self.result[:100] + "..." if len(self.result) > 100 else self.result
            content += f"\n  Result: {result_preview}"
        elif self.error:
            content += f"\n  Error: {self.error}"
        self.update(content)

