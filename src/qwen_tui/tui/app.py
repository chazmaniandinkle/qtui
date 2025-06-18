"""
Main TUI application for Qwen-TUI.

Provides the primary user interface using Textual with chat interface,
status monitoring, and backend management.
"""
import asyncio
from pathlib import Path
from typing import Optional, Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Button, Input, Select, DataTable, Label
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen

from ..backends.manager import BackendManager
from ..backends.base import LLMRequest, BackendStatus
from ..config import Config
from ..logging import get_main_logger
from ..exceptions import QwenTUIError
from ..history import ConversationHistory


class QwenTUIApp(App):
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
        Binding("ctrl+h", "show_help", "Help"),
    ]
    
    # Reactive properties
    current_backend = reactive(None)
    backend_status = reactive("initializing")
    message_count = reactive(0)
    is_compact_layout = reactive(False)
    
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
        
    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        self.logger.info("Qwen-TUI application starting")
        
        try:
            # Initialize backend manager
            await self.backend_manager.initialize()
            
            # Set initial backend
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
        
        # Check initial layout
        self.check_layout()
        
        # Start a new conversation session
        try:
            self.current_session_id = await self.history_manager.start_new_session()
            self.logger.info("Started conversation session", session_id=self.current_session_id)
        except Exception as e:
            self.logger.warning("Failed to start conversation session", error=str(e))
    
    def on_resize(self, event) -> None:
        """Handle terminal resize events."""
        self.check_layout()
    
    def check_layout(self) -> None:
        """Check if we should switch to compact layout based on terminal size."""
        try:
            size = self.size
            should_be_compact = size.width < self.min_width or size.height < self.min_height
            
            if should_be_compact != self.is_compact_layout:
                self.is_compact_layout = should_be_compact
                self.update_layout()
                
                # Show warning for very small screens
                if size.width < 40 or size.height < 15:
                    chat_panel = self.query_one("#chat-panel", ChatPanel)
                    chat_panel.add_system_message(
                        f"Terminal size is very small ({size.width}x{size.height}). "
                        f"For optimal experience, resize to at least 60x20."
                    )
                
        except Exception as e:
            self.logger.debug("Layout check failed", error=str(e))
    
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
                else:
                    main_container.remove_class("ultra-compact")
                
                # Adjust input panel for small screens
                input_panel = self.query_one("#input-panel")
                message_input = self.query_one("#message-input")
                send_button = self.query_one("#send-button")
                
                # Make input take more space, button smaller
                if self.size.width < 40:
                    message_input.styles.width = "65%"
                    send_button.styles.width = "35%"
                    input_panel.styles.height = "2"
                else:
                    message_input.styles.width = "80%"
                    send_button.styles.width = "20%"
                    input_panel.styles.height = "3"
                    
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
                    with ScrollableContainer(id="chat-scroll-container"):
                        yield ChatPanel(id="chat-panel")
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
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.clear_messages()
        
        # Start a new session
        asyncio.create_task(self._start_new_session())
        self.logger.info("Started new conversation")
    
    async def _start_new_session(self) -> None:
        """Start a new conversation session."""
        try:
            self.current_session_id = await self.history_manager.start_new_session()
            self.logger.info("Started new conversation session", session_id=self.current_session_id)
        except Exception as e:
            self.logger.warning("Failed to start new conversation session", error=str(e))
    
    def action_toggle_backends(self) -> None:
        """Toggle backend panel visibility."""
        self.show_backend_panel = not self.show_backend_panel
        backend_panel = self.query_one("#backend-panel", BackendPanel)
        
        if self.show_backend_panel:
            backend_panel.remove_class("hidden")
        else:
            backend_panel.add_class("hidden")
    
    def action_toggle_status(self) -> None:
        """Toggle status panel visibility."""
        self.show_status_panel = not self.show_status_panel
        status_panel = self.query_one("#status-panel", StatusPanel)
        
        if self.show_status_panel:
            status_panel.remove_class("hidden")
        else:
            status_panel.add_class("hidden")
    
    def action_show_help(self) -> None:
        """Show help information."""
        help_text = """
        Qwen-TUI Help
        ============
        
        Keybindings:
        - Ctrl+C: Quit application
        - Ctrl+N: Start new conversation
        - Ctrl+B: Toggle backend panel
        - Ctrl+S: Toggle status panel
        - Ctrl+M: Show model selector
        - Ctrl+H: Show this help
        - Enter: Send message
        - Shift+Enter: New line in input
        
        Commands:
        - /help: Show this help
        - /backends: List available backends
        - /models: Show model selector
        - /switch <backend>: Switch to specific backend
        - /clear: Clear conversation
        - /quit: Quit application
        
        History Commands:
        - /history: Show recent conversations
        - /load <session_id>: Load a conversation
        - /export <format>: Export current conversation (json/txt)
        """
        
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_system_message(help_text)
    
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
            
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            if success:
                chat_panel.add_system_message(f"Switched to model: {model_id} on {backend_type}")
                self.current_backend = backend_type
            else:
                chat_panel.add_error_message(f"Failed to switch to model: {model_id} on {backend_type}")
                
        except Exception as e:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message(f"Error switching model: {str(e)}")
            self.logger.error("Model switch error", error=str(e))
    
    async def send_message(self, message: str) -> None:
        """Send a message to the current backend."""
        if not message.strip():
            return
        
        # Validate message input
        validation_error = self._validate_message_input(message)
        if validation_error:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message(validation_error)
            return
        
        # Handle commands
        if message.startswith('/'):
            await self.handle_command(message)
            return
        
        # Get current backend
        backend = self.backend_manager.get_preferred_backend()
        if not backend:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message("No backends available. Please configure a backend first.")
            return
        
        # Add user message to chat
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_user_message(message)
        
        # Add to conversation history
        user_message = {"role": "user", "content": message}
        self.conversation_history.append(user_message)
        self.message_count += 1
        
        # Save to persistent history
        try:
            backend_name = backend.name if backend else None
            model_name = getattr(backend, '_current_model', None) if backend else None
            await self.history_manager.save_message(user_message, backend_name, model_name)
        except Exception as e:
            self.logger.warning("Failed to save user message to history", error=str(e))
        
        # Add a placeholder assistant message and track its index
        chat_panel.add_assistant_message("")
        assistant_index = len(chat_panel.messages) - 1
        try:
            request = LLMRequest(
                messages=self.conversation_history.copy(),
                stream=True
            )
            chat_panel.show_typing_indicator()
            response_content = ""
            async for response in self.backend_manager.generate(request):
                if response.is_partial and response.delta:
                    response_content += response.delta
                    chat_panel.update_assistant_message(response_content, index=assistant_index)
                elif response.content and not response.is_partial:
                    response_content = response.content
                    chat_panel.update_assistant_message(response_content, index=assistant_index)
            chat_panel.hide_typing_indicator()
            if response_content:
                assistant_message = {"role": "assistant", "content": response_content}
                self.conversation_history.append(assistant_message)
                self.message_count += 1
                try:
                    backend_name = backend.name if backend else None
                    model_name = getattr(backend, '_current_model', None) if backend else None
                    await self.history_manager.save_message(assistant_message, backend_name, model_name)
                except Exception as e:
                    self.logger.warning("Failed to save assistant message to history", error=str(e))
        except Exception as e:
            chat_panel.hide_typing_indicator()
            chat_panel.add_error_message(f"Error: {str(e)}")
            self.logger.error("Error during message send", error=str(e))
    
    async def handle_command(self, command: str) -> None:
        """Handle slash commands."""
        parts = command[1:].split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        
        if cmd == "help":
            self.action_show_help()
        
        elif cmd == "clear":
            self.action_new_conversation()
            chat_panel.add_system_message("Conversation cleared.")
        
        elif cmd == "quit":
            self.action_quit()
        
        elif cmd == "backends":
            backend_info = await self.backend_manager.get_backend_info()
            info_text = "Available Backends:\n"
            for backend_type, info in backend_info.items():
                status = info.get("status", "unknown")
                name = info.get("name", backend_type.value)
                info_text += f"- {name}: {status}\n"
            chat_panel.add_system_message(info_text)
        
        elif cmd == "models":
            self.action_show_model_selector()
        
        elif cmd == "switch" and args:
            backend_name = args[0].lower()
            # Try to switch backend
            # This would need implementation in backend manager
            chat_panel.add_system_message(f"Backend switching to {backend_name} (not implemented yet)")
        
        elif cmd == "history":
            # Show recent conversation sessions
            asyncio.create_task(self._show_conversation_history())
        
        elif cmd == "load" and args:
            # Load a specific conversation session
            session_id = args[0]
            asyncio.create_task(self._load_conversation_session(session_id))
        
        elif cmd == "export" and args:
            # Export current or specified session
            if len(args) >= 2:
                session_id, format_type = args[0], args[1]
            else:
                session_id, format_type = self.current_session_id or "", args[0] if args else "json"
            asyncio.create_task(self._export_conversation_session(session_id, format_type))
        
        else:
            chat_panel.add_error_message(f"Unknown command: /{cmd}")
    
    async def _show_conversation_history(self) -> None:
        """Show recent conversation sessions."""
        try:
            sessions = await self.history_manager.get_recent_sessions(limit=10)
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            
            if not sessions:
                chat_panel.add_system_message("No conversation history found.")
                return
            
            history_text = "Recent Conversations:\n\n"
            for session in sessions:
                started = session.get("started_at", "Unknown")[:16].replace("T", " ")
                preview = session.get("preview", "No content")
                message_count = session.get("message_count", 0)
                session_id = session.get("session_id", "unknown")
                
                history_text += f"• {started} - {message_count} messages\n"
                history_text += f"  ID: {session_id}\n"
                history_text += f"  Preview: {preview}\n\n"
            
            history_text += "Use '/load <session_id>' to load a conversation."
            chat_panel.add_system_message(history_text)
            
        except Exception as e:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message(f"Failed to load conversation history: {str(e)}")
    
    async def _load_conversation_session(self, session_id: str) -> None:
        """Load a specific conversation session."""
        try:
            messages = await self.history_manager.load_session(session_id)
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            
            if not messages:
                chat_panel.add_error_message(f"Session '{session_id}' not found.")
                return
            
            # Clear current conversation
            self.conversation_history.clear()
            chat_panel.clear_messages()
            
            # Load messages into current conversation
            self.conversation_history = messages.copy()
            self.message_count = len(messages)
            
            # Display loaded messages
            for message in messages:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                
                if role == "user":
                    chat_panel.add_user_message(content)
                elif role == "assistant":
                    chat_panel.add_assistant_message(content)
                elif role == "system":
                    chat_panel.add_system_message(content)
            
            # Update current session
            self.current_session_id = session_id
            chat_panel.add_system_message(f"Loaded conversation session: {session_id}")
            self.logger.info("Loaded conversation session", session_id=session_id)
            
        except Exception as e:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message(f"Failed to load session: {str(e)}")
    
    async def _export_conversation_session(self, session_id: str, format_type: str) -> None:
        """Export a conversation session."""
        try:
            if not session_id:
                session_id = self.current_session_id
            
            if not session_id:
                chat_panel = self.query_one("#chat-panel", ChatPanel)
                chat_panel.add_error_message("No session to export.")
                return
            
            # Create export path
            from pathlib import Path
            export_dir = Path.home() / "Downloads"
            export_dir.mkdir(exist_ok=True)
            
            export_file = export_dir / f"qwen_conversation_{session_id}.{format_type}"
            
            success = await self.history_manager.export_session(session_id, export_file, format_type)
            
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            if success:
                chat_panel.add_system_message(f"Exported conversation to: {export_file}")
            else:
                chat_panel.add_error_message(f"Failed to export conversation.")
                
        except Exception as e:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.add_error_message(f"Export failed: {str(e)}")
    
    def _format_user_friendly_error(self, error: Exception) -> str:
        """Format QwenTUI errors in a user-friendly way."""
        error_str = str(error)
        
        # Handle specific backend errors
        if "not found" in error_str.lower() and "model" in error_str.lower():
            return f"Model Error: {error_str}\n\nTip: Try using Ctrl+M to select an available model."
        
        elif "connection" in error_str.lower() or "connect" in error_str.lower():
            return f"Connection Error: {error_str}\n\nTip: Check if your backend service is running."
        
        elif "timeout" in error_str.lower():
            return f"Timeout Error: {error_str}\n\nTip: The request took too long. Try a shorter message or check your connection."
        
        elif "unauthorized" in error_str.lower() or "api key" in error_str.lower():
            return f"Authentication Error: {error_str}\n\nTip: Check your API key configuration."
        
        else:
            return f"Error: {error_str}"
    
    def _format_unexpected_error(self, error: Exception) -> str:
        """Format unexpected errors in a user-friendly way."""
        error_type = type(error).__name__
        error_str = str(error)
        
        # Common network errors
        if "ConnectionError" in error_type or "TimeoutError" in error_type:
            return f"Network Error: Unable to connect to the backend service.\n\nTip: Check if the service is running and accessible."
        
        # Memory or resource errors
        elif "MemoryError" in error_type:
            return f"Memory Error: Not enough memory to process the request.\n\nTip: Try a shorter message or restart the application."
        
        # Generic unexpected error
        else:
            return f"Unexpected Error ({error_type}): {error_str}\n\nTip: Try restarting the application. If the problem persists, check the logs."
    
    def _validate_message_input(self, message: str) -> Optional[str]:
        """Validate user message input and return error message if invalid."""
        message = message.strip()
        
        # Check message length
        if len(message) > 32000:  # Reasonable limit for most models
            return "Message too long. Please keep messages under 32,000 characters."
        
        # Check for excessively long lines (could indicate formatting issues)
        lines = message.split('\n')
        max_line_length = max(len(line) for line in lines) if lines else 0
        if max_line_length > 2000:
            return "Message contains very long lines. Please break up long lines for better readability."
        
        # Check for excessive newlines (could indicate paste formatting issues)
        if message.count('\n') > 200:
            return "Message contains too many line breaks. Please format the text more concisely."
        
        # Check for only whitespace or special characters
        if not any(c.isalnum() for c in message):
            return "Message must contain some alphanumeric characters."
        
        return None


class ChatPanel(Static):
    """Chat display panel showing conversation history."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages = []
        self.typing_indicator_visible = False
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat."""
        self.messages.append(("user", content))
        self.refresh_display()
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the chat."""
        self.messages.append(("assistant", content))
        self.refresh_display()
    
    def add_system_message(self, content: str) -> None:
        """Add a system message to the chat."""
        self.messages.append(("system", content))
        self.refresh_display()
    
    def add_error_message(self, content: str) -> None:
        """Add an error message to the chat."""
        self.messages.append(("error", content))
        self.refresh_display()
    
    def update_assistant_message(self, content: str, index: int = None) -> None:
        """Update the assistant message at a specific index (for streaming)."""
        if index is not None and 0 <= index < len(self.messages):
            self.messages[index] = ("assistant", content)
        elif self.messages:
            self.messages[-1] = ("assistant", content)
        else:
            self.messages.append(("assistant", content))
        self.refresh_display()

    def show_typing_indicator(self) -> None:
        """Show typing indicator."""
        self.typing_indicator_visible = True
        self.refresh_display()
    
    def hide_typing_indicator(self) -> None:
        """Hide typing indicator."""
        self.typing_indicator_visible = False
        self.refresh_display()
    
    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        self.typing_indicator_visible = False
        self.refresh_display()
    
    def refresh_display(self) -> None:
        """Refresh the chat display and scroll to the end."""
        content = ""
        for role, message in self.messages:
            if role == "user":
                content += f"[bold blue]You:[/bold blue] {message}\n\n"
            elif role == "assistant":
                content += f"[bold green]Assistant:[/bold green] {message}\n\n"
            elif role == "system":
                content += f"[dim italic]{message}[/dim italic]\n\n"
            elif role == "error":
                content += f"[bold red]Error:[/bold red] {message}\n\n"
        if self.typing_indicator_visible:
            content += "[dim]Assistant is typing...[/dim]"
        self.update(content)
        self.scroll_visible()
        # Scroll to the end if inside a ScrollableContainer
        parent = self.parent
        if parent and hasattr(parent, "scroll_end"):
            parent.scroll_end(animate=False)


class InputPanel(Container):
    """Input panel for user messages."""
    
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(placeholder="Type your message...", id="message-input")
            yield Button("Send", id="send-button", variant="primary")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()
        if message:
            app = self.app
            await app.send_message(message)
            event.input.value = ""
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        if event.button.id == "send-button":
            input_widget = self.query_one("#message-input", Input)
            message = input_widget.value.strip()
            if message:
                app = self.app
                await app.send_message(message)
                input_widget.value = ""


class BackendPanel(Container):
    """Panel showing backend information and controls."""
    
    def compose(self) -> ComposeResult:
        yield Static("Backend Panel", classes="panel-title")
        yield Static("No backend information available", id="backend-info")


class StatusPanel(Container):
    """Panel showing application status and metrics."""
    
    def compose(self) -> ComposeResult:
        yield Static("Status Panel", classes="panel-title")
        yield Static("Initializing...", id="status-info")


class ModelSelectorScreen(ModalScreen):
    """Modal screen for selecting models across backends."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select_model", "Select"),
    ]
    
    def __init__(self, backend_manager: BackendManager, **kwargs):
        super().__init__(**kwargs)
        self.backend_manager = backend_manager
        self.models = {}
        self.selected_row = 0
    
    def compose(self) -> ComposeResult:
        with Container(id="model-selector"):
            yield Label("Select a Model", id="selector-title")
            yield DataTable(id="models-table", show_header=True, show_cursor=True)
            with Horizontal(id="selector-buttons"):
                yield Button("Select", id="select-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")
    
    async def on_mount(self) -> None:
        """Load models and adjust layout when mounted."""
        self.adjust_for_screen_size()
        await self.load_models()
    
    def adjust_for_screen_size(self) -> None:
        """Adjust the model selector for small screens."""
        try:
            app_size = self.app.size
            
            # For very small screens, adjust table columns
            if app_size.width < 70:
                # This will be handled in the load_models method
                pass
                
        except Exception as e:
            pass
    
    async def load_models(self) -> None:
        """Load all available models from backends."""
        try:
            table = self.query_one("#models-table", DataTable)
            
            # Adjust columns based on screen size
            app_size = self.app.size
            if app_size.width < 70:
                # Compact columns for small screens
                table.add_columns("Backend", "Model", "Status")
            else:
                # Full columns for larger screens
                table.add_columns("Backend", "Model", "Type", "Status")
            
            # Get all models
            all_models = await self.backend_manager.get_all_models()
            current_models = await self.backend_manager.get_current_models()
            
            row_data = []
            for backend_name, models in all_models.items():
                current_model = current_models.get(backend_name)
                
                for model in models:
                    model_id = model['id']
                    status = "● Current" if model_id == current_model else "Available"
                    
                    # Truncate model ID for small screens
                    display_model_id = model_id
                    if app_size.width < 70 and len(model_id) > 30:
                        display_model_id = model_id[:27] + "..."
                    
                    if app_size.width < 70:
                        # Compact layout
                        table.add_row(
                            backend_name.title()[:8],  # Shorter backend name
                            display_model_id,
                            status[:12]  # Shorter status
                        )
                    else:
                        # Full layout
                        table.add_row(
                            backend_name.title(),
                            display_model_id,
                            model.get('object', 'model'),
                            status
                        )
                    
                    # Store model data for selection
                    row_data.append((backend_name, model_id))
            
            self.models = dict(enumerate(row_data))
            
        except Exception as e:
            error_msg = f"Failed to load models: {str(e)}"
            table = self.query_one("#models-table", DataTable)
            table.add_row("Error", error_msg, "", "")
    
    def action_cancel(self) -> None:
        """Cancel model selection."""
        self.dismiss(None)
    
    def action_select_model(self) -> None:
        """Select the currently highlighted model."""
        table = self.query_one("#models-table", DataTable)
        
        if table.cursor_row is not None and table.cursor_row in self.models:
            backend_type, model_id = self.models[table.cursor_row]
            self.dismiss((backend_type, model_id))
        else:
            self.dismiss(None)
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "select-btn":
            self.action_select_model()
        elif event.button.id == "cancel-btn":
            self.action_cancel()
    
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle table row selection."""
        self.selected_row = event.row_key
        # Auto-select when row is clicked
        if event.row_key in self.models:
            backend_type, model_id = self.models[event.row_key]
            self.dismiss((backend_type, model_id))