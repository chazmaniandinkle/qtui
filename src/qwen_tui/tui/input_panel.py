from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Key
from textual.widgets import Button, Input


class InputPanel(Container):
    """Input panel for user messages."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(placeholder="Type your message...", id="message-input")
            yield Button("Send", id="send-button", variant="primary")

    def on_key(self, event: Key) -> None:
        """Handle key events so global shortcuts work while typing."""
        logger = self.app.logger
        if event.key == "ctrl+n":
            logger.debug("InputPanel: Ctrl+N triggered - New conversation")
            self.app.action_new_conversation()
            event.prevent_default()
        elif event.key == "ctrl+b":
            logger.debug("InputPanel: Ctrl+B triggered - Toggle backends")
            self.app.action_toggle_backends()
            event.prevent_default()
        elif event.key == "ctrl+s":
            logger.debug("InputPanel: Ctrl+S triggered - Toggle status")
            self.app.action_toggle_status()
            event.prevent_default()
        elif event.key == "ctrl+m":
            logger.debug("InputPanel: Ctrl+M triggered - Model selector")
            self.app.action_show_model_selector()
            event.prevent_default()
        elif event.key == "ctrl+h":
            logger.debug("InputPanel: Ctrl+H triggered - Help")
            self.app.action_show_help()
            event.prevent_default()
        elif event.key == "escape":
            logger.debug("InputPanel: Escape pressed - Clearing focus")
            input_widget = self.query_one("#message-input", Input)
            input_widget.blur()
            event.prevent_default()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()
        if message:
            app = self.app
            if message.startswith("/"):
                await app.handle_command(message)
            else:
                await app.send_message(message)
            event.input.value = ""

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        if event.button.id == "send-button":
            input_widget = self.query_one("#message-input", Input)
            message = input_widget.value.strip()
            if message:
                app = self.app
                if message.startswith("/"):
                    await app.handle_command(message)
                else:
                    await app.send_message(message)
                input_widget.value = ""

