#!/usr/bin/env python3
"""
Test script to identify focus and key event handling issues.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.events import Key


class FocusTestApp(App):
    """Test app to identify focus and key handling issues."""
    
    TITLE = "Focus and Key Event Test"
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "test_shortcut", "Test"),
        Binding("escape", "clear_focus", "Clear Focus"),
        Binding("tab", "next_focus", "Next Focus"),
    ]
    
    def __init__(self):
        super().__init__()
        self.event_log = []
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Focus and Key Event Debugging", id="title")
            yield Static("Test different scenarios:", id="instructions")
            yield Static("1. Type in input field, then try Ctrl+N", id="test1")
            yield Static("2. Click button, then try Ctrl+N", id="test2")
            yield Static("3. Press Tab to change focus, then try Ctrl+N", id="test3")
            yield Static("4. Press Escape to clear focus, then try Ctrl+N", id="test4")
            yield Static("", id="event-log")
            
            with Horizontal():
                yield Input(placeholder="Type here...", id="test-input")
                yield Button("Test Button", id="test-button")
            
            yield Static("Event Log:", id="log-title")
            yield Static("", id="log-content")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app."""
        self.log_event("App mounted")
        # Try to get the input focused initially
        input_widget = self.query_one("#test-input", Input)
        input_widget.focus()
        self.log_event("Input widget focused on mount")
    
    def log_event(self, message: str) -> None:
        """Log an event to the display."""
        self.event_log.append(message)
        if len(self.event_log) > 10:
            self.event_log = self.event_log[-10:]  # Keep last 10 events
        
        log_content = self.query_one("#log-content", Static)
        log_text = "\n".join(f"• {event}" for event in self.event_log[-5:])
        log_content.update(log_text)
    
    def action_test_shortcut(self) -> None:
        """Test Ctrl+N shortcut."""
        focused = self.focused
        focused_info = f"{type(focused).__name__} id='{focused.id}'" if focused else "None"
        self.log_event(f"✓ Ctrl+N worked! Focused: {focused_info}")
    
    def action_clear_focus(self) -> None:
        """Clear focus from all widgets."""
        if self.focused:
            self.focused.blur()
        self.log_event("Focus cleared with Escape")
    
    def action_next_focus(self) -> None:
        """Move to next focusable widget."""
        # Let the default behavior handle this
        self.log_event("Tab pressed - focus should move")
    
    def action_quit(self) -> None:
        """Quit the app."""
        self.log_event("Quitting with Ctrl+C")
        self.exit()
    
    def on_key(self, event: Key) -> None:
        """Log all key events for debugging."""
        self.log_event(f"Key: {event.key} (focused: {type(self.focused).__name__ if self.focused else 'None'})")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "test-button":
            self.log_event("Button pressed - button now has focus")
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self.log_event(f"Input changed: '{event.value}' (len={len(event.value)})")
    
    def on_focus(self, event) -> None:
        """Track focus changes."""
        widget_info = f"{type(event.widget).__name__} id='{event.widget.id}'"
        self.log_event(f"Focus gained: {widget_info}")
    
    def on_blur(self, event) -> None:
        """Track blur events."""
        widget_info = f"{type(event.widget).__name__} id='{event.widget.id}'"
        self.log_event(f"Focus lost: {widget_info}")


if __name__ == "__main__":
    print("🧪 Focus and Key Event Test")
    print("   Testing focus handling and key event propagation")
    print("   This will help identify why keyboard shortcuts aren't working")
    print()
    print("   Test scenarios:")
    print("   1. Type in input, then try Ctrl+N")
    print("   2. Click button, then try Ctrl+N") 
    print("   3. Use Tab to change focus, then try Ctrl+N")
    print("   4. Use Escape to clear focus, then try Ctrl+N")
    print()
    
    try:
        app = FocusTestApp()
        app.run()
    except KeyboardInterrupt:
        print("\n🔚 Focus test completed!")