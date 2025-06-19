"""
Main TUI application for Qwen-TUI.

Provides the primary user interface using Textual with chat interface,
status monitoring, and backend management.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.events import Click, Key
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Tree,
)

from ..backends.base import BackendStatus, LLMRequest
from ..backends.manager import BackendManager
from ..config import Config
from ..exceptions import QwenTUIError
from ..history import ConversationHistory
from ..logging import get_main_logger

# Import thinking components - will be created in this file for now
try:
    from .thinking import ThinkingManager
except ImportError:
    # Fallback if thinking module not available
    ThinkingManager = None

# Import permission system
from .permission_manager import (
    TUIPermissionManager,
    get_permission_manager,
    set_permission_manager,
)
from .backend_panel import BackendPanel
from .input_panel import InputPanel
from .status_panel import StatusPanel
from .model_selector import ModelSelectorScreen
from .widgets import ChatMessage, ThinkingWidget, ActionWidget
from .chat_handlers import ChatHandlersMixin

class QwenTUIApp(ChatHandlersMixin, App):
    """Main Qwen-TUI application."""

    CSS_PATH = Path(__file__).parent / "styles.css"
    TITLE = "Qwen-TUI"
    SUB_TITLE = "AI-Powered Terminal Coding Assistant"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "new_conversation", "New Chat"),
        Binding("ctrl+b", "toggle_backends", "Backend Panel"),
        Binding("ctrl+s", "toggle_status", "Status Panel"),
        Binding("ctrl+m", "show_model_selector", "Model Selector"),
        Binding("ctrl+p", "show_permissions", "Permissions"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("escape", "clear_focus", "Clear Focus"),
    ]

    # Reactive properties
    current_backend = reactive(None)
    backend_status = reactive("initializing")
    message_count = reactive(0)
    is_compact_layout = reactive(False)

    # Allow tests to override size property
    @property
    def size(self):  # type: ignore[override]
        return getattr(self, "_mock_size", super().size)

    @size.setter
    def size(self, value):  # type: ignore[override]
        self._mock_size = value

    def __init__(self, backend_manager: BackendManager, config: Config):
        super().__init__()
        self.backend_manager = backend_manager
        self.config = config
        self.logger = get_main_logger()

        # Application state
        self.conversation_history = []
        self.current_request = None
        self.show_backend_panel = False
        self.show_status_panel = True
        self.min_width = 60  # Minimum width before switching to compact layout
        self.min_height = 20  # Minimum height for proper functionality

        # History management
        self.history_manager = ConversationHistory(config)
        self.current_session_id: Optional[str] = None

        # Thinking system
        if ThinkingManager:
            protocol_client = None
            if getattr(config, "use_protocol", False):
                from ..protocol import ProtocolClient

                protocol_client = ProtocolClient(config.protocol_url)
            self.thinking_manager = ThinkingManager(
                backend_manager, config, protocol_client=protocol_client
            )
        else:
            self.thinking_manager = None
        self.current_thinking_widget: Optional[ThinkingWidget] = None
        self.active_action_widgets: Dict[str, ActionWidget] = {}

        # Permission system
        working_directory = getattr(config, "working_directory", None)
        yolo_mode = getattr(config, "yolo_mode", False)
        self.permission_manager = TUIPermissionManager(
            self, working_directory, yolo_mode
        )
        set_permission_manager(self.permission_manager)

    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        self.logger.info("Qwen-TUI application starting")
        try:
            await self.backend_manager.initialize()
            preferred = self.backend_manager.get_preferred_backend()
            if preferred:
                self.current_backend = preferred.name
                self.backend_status = "ready"
                self.logger.info(f"Using backend: {preferred.name}")
            else:
                self.backend_status = "no_backends"
                self.logger.warning("No backends available")
        except Exception as e:
            self.logger.error("Failed to initialize application", error=str(e))
            self.backend_status = "error"

        # Initialize thinking system
        if self.thinking_manager:
            try:
                await self.thinking_manager.initialize()
                self._setup_thinking_callbacks()
                self.logger.info("Thinking system initialized")
            except Exception as e:
                self.logger.warning(
                    "Failed to initialize thinking system", error=str(e)
                )
        else:
            self.logger.info(
                "Thinking system not available - using direct backend mode"
            )

        self.check_layout()
        # Start a new conversation session
        try:
            self.current_session_id = await self.history_manager.start_new_session()
            self.logger.info(
                "Started conversation session", session_id=self.current_session_id
            )
            self.clear_chat()
            self.add_system_message(
                "Welcome to Qwen-TUI! 🧠 Enhanced with thinking capabilities."
            )
        except Exception as e:
            self.logger.warning("Failed to start conversation session", error=str(e))

    def _setup_thinking_callbacks(self):
        """Setup callbacks for thinking system UI updates."""
        if self.thinking_manager:
            self.thinking_manager.set_ui_callbacks(
                on_thinking_update=self._on_thinking_update,
                on_action_start=self._on_action_start,
                on_action_complete=self._on_action_complete,
                on_action_error=self._on_action_error,
                on_thinking_complete=self._on_thinking_complete,
            )

    async def _on_thinking_update(self, thinking_text: str):
        """Handle thinking text updates."""
        if self.current_thinking_widget:
            self.current_thinking_widget.update_thinking_text(thinking_text)

    async def _on_action_start(self, call_id: str, tool_name: str, parameters: dict):
        """Handle start of tool action."""
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        action_widget = ActionWidget("tool_call", tool_name, "running")
        action_widget.set_parameters(parameters)

        await chat_scroll.mount(action_widget)
        action_widget.scroll_visible()

        self.active_action_widgets[call_id] = action_widget

    async def _on_action_complete(self, call_id: str, tool_name: str, result: Any):
        """Handle completion of tool action."""
        if call_id in self.active_action_widgets:
            action_widget = self.active_action_widgets[call_id]
            action_widget.set_result(str(result))
            del self.active_action_widgets[call_id]

    async def _on_action_error(self, call_id: str, tool_name: str, error: str):
        """Handle error in tool action."""
        if call_id in self.active_action_widgets:
            action_widget = self.active_action_widgets[call_id]
            action_widget.set_error(error)
            del self.active_action_widgets[call_id]

    async def _on_thinking_complete(self, final_response: str):
        """Handle completion of thinking process."""
        if self.current_thinking_widget:
            self.current_thinking_widget.stop_thinking()
            full_thoughts = self.thinking_manager.get_thinking_state().full_thoughts
            self.current_thinking_widget.set_full_thoughts(full_thoughts)
            self.current_thinking_widget = None

    def on_resize(self, event) -> None:
        """Handle terminal resize events."""
        self.check_layout()

    def check_layout(self) -> None:
        """Check if we should switch to compact layout based on terminal size."""
        try:
            size = self.size
            should_be_compact = (
                size.width < self.min_width or size.height < self.min_height
            )
            if should_be_compact != self.is_compact_layout:
                self.is_compact_layout = should_be_compact
                self.update_layout()
                # Show warning for very small screens
                if size.width < 40 or size.height < 15:
                    self.add_system_message(
                        f"Terminal size is very small ({size.width}x{size.height}). For optimal experience, resize to at least 60x20."
                    )
        except Exception as e:
            self.logger.debug("Layout update failed", error=str(e))

    def update_layout(self) -> None:
        """Update the layout based on current compact status."""
        try:
            main_container = self.query_one("#main-container")
            chat_area = self.query_one("#chat-area")
            side_panels = self.query_one("#side-panels")

            if self.is_compact_layout:
                # Switch to compact layout
                main_container.add_class("compact-layout")
                chat_area.styles.width = "100%"
                side_panels.add_class("hidden")
                self.show_backend_panel = False
                self.show_status_panel = False

                # Check for ultra-compact mode (very small screens)
                if self.size.width < 40 or self.size.height < 15:
                    main_container.add_class("ultra-compact")
                    # Provide user guidance for ultra-compact mode
                    if self.size.width < 30:
                        self.add_system_message(
                            "⚠️ Terminal extremely small. Consider resizing for better experience."
                        )
                else:
                    main_container.remove_class("ultra-compact")

                # Adjust input panel for small screens
                input_panel = self.query_one("#input-panel")
                message_input = self.query_one("#message-input")
                send_button = self.query_one("#send-button")

                # Make input take more space, button smaller
                if self.size.width < 40:
                    message_input.styles.width = "70%"
                    send_button.styles.width = "30%"
                    input_panel.styles.height = "2"
                    # Update placeholder for small screens
                    message_input.placeholder = "Message..."
                else:
                    message_input.styles.width = "80%"
                    send_button.styles.width = "20%"
                    input_panel.styles.height = "3"
                    message_input.placeholder = "Type your message..."

            else:
                # Switch to normal layout
                main_container.remove_class("compact-layout")
                main_container.remove_class("ultra-compact")
                chat_area.styles.width = "70%"
                side_panels.remove_class("hidden")

                # Reset input panel proportions
                input_panel = self.query_one("#input-panel")
                message_input = self.query_one("#message-input")
                send_button = self.query_one("#send-button")
                message_input.styles.width = "80%"
                send_button.styles.width = "20%"
                input_panel.styles.height = "10%"

        except Exception as e:
            self.logger.debug("Layout update failed", error=str(e))

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header()

        with Container(id="main-container"):
            with Horizontal():
                # Main chat area
                with Vertical(id="chat-area"):
                    yield ScrollableContainer(id="chat-scroll")
                    yield InputPanel(id="input-panel")

                # Side panels (initially hidden)
                with Vertical(id="side-panels", classes="hidden"):
                    yield BackendPanel(id="backend-panel", classes="hidden")
                    yield StatusPanel(id="status-panel")

        yield Footer()

    def action_quit(self) -> None:
        """Handle quit action."""
        self.logger.info("Application quit requested")
        self.exit()

    def action_new_conversation(self) -> None:
        """Start a new conversation."""
        self.conversation_history.clear()
        self.message_count = 0
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        # Clear chat messages depending on implementation
        if hasattr(chat_scroll, "clear_messages"):
            chat_scroll.clear_messages()
        else:
            for child in list(chat_scroll.children):
                child.remove()
        # Start a new session
        asyncio.create_task(self._start_new_session())
        self.logger.info("Started new conversation")
        # Provide user feedback
        self.add_system_message("New conversation started. (Ctrl+N)")

    async def _start_new_session(self) -> None:
        """Start a new conversation session."""
        try:
            self.current_session_id = await self.history_manager.start_new_session()
            self.logger.info(
                "Started new conversation session", session_id=self.current_session_id
            )
        except Exception as e:
            self.logger.warning(
                "Failed to start new conversation session", error=str(e)
            )

    def action_toggle_backends(self) -> None:
        """Toggle backend panel visibility."""
        self.show_backend_panel = not self.show_backend_panel
        backend_panel = self.query_one("#backend-panel", BackendPanel)
        side_panels = self.query_one("#side-panels")

        if self.show_backend_panel:
            backend_panel.remove_class("hidden")
            side_panels.remove_class("hidden")
            self.logger.debug("Backend panel shown")
            # Provide user feedback
            self.add_system_message("Backend panel shown. (Ctrl+B)")
        else:
            backend_panel.add_class("hidden")
            # Hide side panels container if both panels are hidden
            status_panel = self.query_one("#status-panel", StatusPanel)
            if not self.show_status_panel or status_panel.has_class("hidden"):
                side_panels.add_class("hidden")
            self.logger.debug("Backend panel hidden")
            # Provide user feedback
            self.add_system_message("Backend panel hidden. (Ctrl+B)")

    def action_toggle_status(self) -> None:
        """Toggle status panel visibility."""
        self.show_status_panel = not self.show_status_panel
        status_panel = self.query_one("#status-panel", StatusPanel)
        side_panels = self.query_one("#side-panels")

        if self.show_status_panel:
            status_panel.remove_class("hidden")
            side_panels.remove_class("hidden")
            self.logger.debug("Status panel shown")
            # Provide user feedback
            self.add_system_message("Status panel shown. (Ctrl+S)")
        else:
            status_panel.add_class("hidden")
            # Hide side panels container if both panels are hidden
            backend_panel = self.query_one("#backend-panel", BackendPanel)
            if not self.show_backend_panel or backend_panel.has_class("hidden"):
                side_panels.add_class("hidden")
            self.logger.debug("Status panel hidden")
            # Provide user feedback
            self.add_system_message("Status panel hidden. (Ctrl+S)")

    def action_show_help(self) -> None:
        """Show help information."""
        help_text = """🎮 Qwen-TUI Keyboard Shortcuts:

⌨️  Global Shortcuts:
• Ctrl+N: Start new conversation
• Ctrl+B: Toggle backend panel
• Ctrl+S: Toggle status panel  
• Ctrl+M: Open model selector
• Ctrl+P: Show permissions
• Ctrl+H: Show this help
• Escape: Clear input focus

💬 Chat Commands:
• /help: Show help
• /clear: Clear conversation
• /history: Recent conversations
• /load <id>: Load conversation
• /export <format>: Export chat
• /backends: Backend information
• /models: Open model selector
• /permissions: Show permission status
• /permissions clear <tool>: Clear tool preferences
• /permissions yolo: Toggle YOLO mode

💡 Tips:
• Panels update in real-time
• Click thinking widget to expand
• Use Escape to enable shortcuts when typing
• Backend panel shows connection status
• Status panel shows system information"""
        self.add_system_message(help_text)

    def action_clear_focus(self) -> None:
        """Clear focus from input widgets to enable keyboard shortcuts."""
        try:
            # Clear focus from the input widget
            input_widget = self.query_one("#message-input", Input)
            input_widget.blur()
            self.logger.debug("Focus cleared from input widget")
            # Provide subtle feedback
            self.add_system_message("Focus cleared. Global shortcuts enabled.")
        except Exception as e:
            self.logger.debug("Failed to clear focus", error=str(e))
            self.add_system_message("⚠️ Failed to clear focus.")

    def on_key(self, event: Key) -> None:
        """Handle key events for debugging and global shortcuts."""
        # Log key events for debugging (can be removed in production)
        if event.key.startswith("ctrl+"):
            self.logger.debug(f"Key event received at app level: {event.key}")

        # Don't consume the event, let it propagate normally
        # This just provides debugging visibility

    def action_show_model_selector(self) -> None:
        """Show the model selector modal."""

        def on_model_selected(result):
            if result:
                backend_type, model_id = result
                self.logger.info(f"Selected model {model_id} on {backend_type}")
                # Switch to the selected model
                asyncio.create_task(self._switch_model(backend_type, model_id))

        model_selector = ModelSelectorScreen(self.backend_manager)
        self.push_screen(model_selector, on_model_selected)

    async def _switch_model(self, backend_type: str, model_id: str) -> None:
        """Switch to the selected model."""
        try:
            from ..config import BackendType

            backend_enum = BackendType(backend_type.lower())
            success = await self.backend_manager.switch_model(backend_enum, model_id)

            chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
            if success:
                # Mount success message
                success_message = ChatMessage(
                    "system", f"Switched to model: {model_id} on {backend_type}"
                )
                await chat_scroll.mount(success_message)
                success_message.scroll_visible()
                self.current_backend = backend_type
            else:
                # Mount error message
                error_message = ChatMessage(
                    "error", f"Failed to switch to model: {model_id} on {backend_type}"
                )
                await chat_scroll.mount(error_message)
                error_message.scroll_visible()

        except Exception as e:
            error_msg = ChatMessage("error", f"Error switching model: {str(e)}")
            await chat_scroll.mount(error_msg)
            error_msg.scroll_visible()
            self.logger.error("Model switch error", error=str(e))

    def action_show_permissions(self) -> None:
        """Show permission system status and controls."""
        try:
            status = self.permission_manager.get_permission_status()
            preferences = self.permission_manager.preferences

            permissions_text = "🔒 Permission System Status:\n\n"

            # YOLO mode status
            if status["yolo_mode"]:
                permissions_text += (
                    "⚠️ YOLO Mode: ENABLED (All permissions bypassed)\n\n"
                )
            else:
                permissions_text += "🛡️ Security Mode: ACTIVE\n\n"

            # Always allowed tools
            if preferences.always_allow:
                permissions_text += "✅ Always Allowed Tools:\n"
                for tool in sorted(preferences.always_allow):
                    permissions_text += f"  • {tool}\n"
                permissions_text += "\n"

            # Always denied tools
            if preferences.always_deny:
                permissions_text += "❌ Always Denied Tools:\n"
                for tool in sorted(preferences.always_deny):
                    permissions_text += f"  • {tool}\n"
                permissions_text += "\n"

            # Status summary
            prefs_summary = status["preferences"]
            permissions_text += f"📊 Statistics:\n"
            permissions_text += (
                f"  • Total preferences: {prefs_summary['total_preferences']}\n"
            )
            permissions_text += f"  • Pending requests: {status['pending_requests']}\n"
            permissions_text += (
                f"  • Permission history: {status['permission_history']}\n\n"
            )

            permissions_text += "💡 Commands:\n"
            permissions_text += "• /permissions clear <tool>: Clear tool preferences\n"
            permissions_text += "• /permissions yolo: Toggle YOLO mode\n"
            permissions_text += "• Ctrl+P: Show this status\n"

            permission_message = ChatMessage("system", permissions_text)
            chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
            chat_scroll.mount(permission_message)
            permission_message.scroll_visible()

        except Exception as e:
            self.logger.error("Error showing permissions", error=str(e))
            self.add_error_message(f"Failed to show permissions: {str(e)}")



