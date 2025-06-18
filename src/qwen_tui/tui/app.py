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
        self.logger.info("Started new conversation")
    
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
        self.conversation_history.append({"role": "user", "content": message})
        self.message_count += 1
        
        try:
            # Create request
            request = LLMRequest(
                messages=self.conversation_history.copy(),
                stream=True
            )
            
            # Show typing indicator
            chat_panel.show_typing_indicator()
            
            # Generate response
            response_content = ""
            async for response in self.backend_manager.generate(request):
                if response.is_partial and response.delta:
                    response_content += response.delta
                    chat_panel.update_assistant_message(response_content)
                elif response.content and not response.is_partial:
                    response_content = response.content
                    chat_panel.update_assistant_message(response_content)
            
            # Hide typing indicator
            chat_panel.hide_typing_indicator()
            
            # Add assistant message to history
            if response_content:
                self.conversation_history.append({"role": "assistant", "content": response_content})
                self.message_count += 1
                
        except QwenTUIError as e:
            chat_panel.hide_typing_indicator()
            chat_panel.add_error_message(f"Error: {str(e)}")
            self.logger.error("Failed to generate response", error=str(e))
        except Exception as e:
            chat_panel.hide_typing_indicator()
            chat_panel.add_error_message(f"Unexpected error: {str(e)}")
            self.logger.error("Unexpected error during message generation", 
                            error=str(e), 
                            error_type=type(e).__name__)
    
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
        
        else:
            chat_panel.add_error_message(f"Unknown command: /{cmd}")


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
    
    def update_assistant_message(self, content: str) -> None:
        """Update the last assistant message (for streaming)."""
        if self.messages and self.messages[-1][0] == "assistant":
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
        """Refresh the chat display."""
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