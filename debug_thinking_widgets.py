#!/usr/bin/env python3
"""
Debug script to isolate thinking widget layout issues.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button
from textual.binding import Binding
from textual.timer import Timer
from textual.events import Click
from typing import Optional

# Import the widget classes from app.py
from qwen_tui.tui.app import ThinkingWidget, ActionWidget, InputPanel


class ThinkingWidgetDebugApp(App):
    """Debug app for thinking widget layout issues."""
    
    CSS_PATH = Path(__file__).parent / "src" / "qwen_tui" / "tui" / "styles.css"
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("1", "add_thinking", "Add Thinking"),
        Binding("2", "add_action", "Add Action"),
        Binding("3", "clear_widgets", "Clear"),
        Binding("4", "stress_test", "Stress Test"),
    ]
    
    TITLE = "Thinking Widget Debug"
    
    def __init__(self):
        super().__init__()
        self.widget_count = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="debug-container"):
            yield Static("Thinking Widget Layout Debug", id="title")
            yield Static("Press 1-4 to test widget interactions", id="instructions")
            yield Static("Watch for layout corruption around input area", id="warning")
            yield ScrollableContainer(
                Static("Chat area - widgets will appear here"),
                id="chat-scroll"
            )
            yield InputPanel(id="input-panel")
        yield Footer()
    
    def action_add_thinking(self) -> None:
        """Add a thinking widget to test layout."""
        self.widget_count += 1
        thinking_widget = ThinkingWidget(f"Test thinking process {self.widget_count}")
        thinking_widget.start_thinking()
        
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        chat_scroll.mount(thinking_widget)
        
        # Test with full thoughts
        thinking_widget.set_full_thoughts(f"This is a longer thinking process for widget {self.widget_count}. " * 5)
    
    def action_add_action(self) -> None:
        """Add an action widget to test layout."""
        self.widget_count += 1
        action_widget = ActionWidget("tool_call", f"test_tool_{self.widget_count}")
        action_widget.set_parameters({"param1": "value1", "param2": "value2"})
        
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        chat_scroll.mount(action_widget)
        
        # Simulate completion after 2 seconds
        self.set_timer(2.0, lambda: action_widget.set_result(f"Tool completed successfully for widget {self.widget_count}"))
    
    def action_clear_widgets(self) -> None:
        """Clear all widgets."""
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        for child in list(chat_scroll.children):
            if isinstance(child, (ThinkingWidget, ActionWidget)):
                child.remove()
        self.widget_count = 0
    
    def action_stress_test(self) -> None:
        """Add multiple widgets quickly to stress test layout."""
        for i in range(5):
            self.set_timer(i * 0.5, self.action_add_thinking)
            self.set_timer(i * 0.5 + 0.25, self.action_add_action)


async def main():
    """Run the debug test."""
    app = ThinkingWidgetDebugApp()
    await app.run_async()


if __name__ == "__main__":
    print("🐛 Thinking Widget Layout Debug")
    print("   Testing thinking and action widgets for layout corruption")
    print("   Controls:")
    print("   - 1: Add thinking widget")
    print("   - 2: Add action widget") 
    print("   - 3: Clear all widgets")
    print("   - 4: Stress test (add multiple widgets)")
    print("   - Watch for layout issues around input panel")
    print("   - Ctrl+C: Exit")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔚 Debug test completed!")