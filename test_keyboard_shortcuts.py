#!/usr/bin/env python3
"""
Test script to isolate and verify keyboard shortcut functionality.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Vertical
from textual.binding import Binding


class KeyboardTestApp(App):
    """Minimal app to test keyboard shortcuts."""
    
    TITLE = "Keyboard Shortcut Test"
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "new_action", "New"),
        Binding("ctrl+b", "backend_action", "Backend"),
        Binding("ctrl+s", "status_action", "Status"),
        Binding("ctrl+m", "model_action", "Model"),
        Binding("ctrl+h", "help_action", "Help"),
        Binding("f1", "test_key", "Test F1"),
    ]
    
    def __init__(self):
        super().__init__()
        self.last_action = "None"
        self.action_count = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Keyboard Shortcut Test", id="title")
            yield Static("Press keyboard shortcuts to test them:", id="instructions")
            yield Static("• Ctrl+N: New", id="help1")
            yield Static("• Ctrl+B: Backend", id="help2")
            yield Static("• Ctrl+S: Status", id="help3")
            yield Static("• Ctrl+M: Model", id="help4")
            yield Static("• Ctrl+H: Help", id="help5")
            yield Static("• F1: Test key", id="help6")
            yield Static("• Ctrl+C: Quit", id="help7")
            yield Static("", id="status")
            yield Input(placeholder="Type here to test input focus...", id="test-input")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app."""
        self.update_status("App mounted - try keyboard shortcuts!")
    
    def update_status(self, message: str) -> None:
        """Update the status display."""
        status = self.query_one("#status", Static)
        self.action_count += 1
        status.update(f"[{self.action_count}] {message}")
    
    def action_new_action(self) -> None:
        """Test Ctrl+N."""
        self.last_action = "new_action"
        self.update_status("✓ Ctrl+N pressed - New action triggered!")
    
    def action_backend_action(self) -> None:
        """Test Ctrl+B."""
        self.last_action = "backend_action"
        self.update_status("✓ Ctrl+B pressed - Backend action triggered!")
    
    def action_status_action(self) -> None:
        """Test Ctrl+S."""
        self.last_action = "status_action"
        self.update_status("✓ Ctrl+S pressed - Status action triggered!")
    
    def action_model_action(self) -> None:
        """Test Ctrl+M."""
        self.last_action = "model_action"
        self.update_status("✓ Ctrl+M pressed - Model action triggered!")
    
    def action_help_action(self) -> None:
        """Test Ctrl+H."""
        self.last_action = "help_action"
        self.update_status("✓ Ctrl+H pressed - Help action triggered!")
    
    def action_test_key(self) -> None:
        """Test F1."""
        self.last_action = "test_key"
        self.update_status("✓ F1 pressed - Test key triggered!")
    
    def action_quit(self) -> None:
        """Test Ctrl+C."""
        self.last_action = "quit"
        self.update_status("✓ Ctrl+C pressed - Quitting...")
        self.exit()
    
    def on_key(self, event) -> None:
        """Handle any key press to show debugging info."""
        # Show what key was pressed
        self.update_status(f"Key pressed: {event.key} (no binding found)")


if __name__ == "__main__":
    print("🧪 Keyboard Shortcut Test")
    print("   Testing if keyboard shortcuts work in isolation")
    print("   Expected shortcuts:")
    print("   - Ctrl+N: New action")
    print("   - Ctrl+B: Backend action")
    print("   - Ctrl+S: Status action")
    print("   - Ctrl+M: Model action")
    print("   - Ctrl+H: Help action")
    print("   - F1: Test key")
    print("   - Ctrl+C: Quit")
    print()
    
    try:
        app = KeyboardTestApp()
        app.run()
    except KeyboardInterrupt:
        print("\n🔚 Keyboard test completed!")