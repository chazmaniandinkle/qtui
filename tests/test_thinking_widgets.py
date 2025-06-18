#!/usr/bin/env python3
"""
Test script for thinking widgets in Qwen-TUI.

Tests the ThinkingWidget and ActionWidget components independently.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding

from qwen_tui.tui.app import ThinkingWidget, ActionWidget


class ThinkingTestApp(App):
    """Test app for thinking widgets."""
    
    CSS = """
    .thinking-widget {
        background: $surface;
        border-left: solid $warning;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
    }
    
    .thinking-widget:hover {
        background: $accent;
    }
    
    .action-widget {
        background: $surface;
        border-left: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
    }
    
    #test-container {
        height: 100%;
        padding: 1;
    }
    
    #controls {
        height: auto;
        margin-bottom: 1;
    }
    
    #widgets-area {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("t", "test_thinking", "Test Thinking"),
        Binding("a", "test_action", "Test Action"),
        Binding("s", "stop_thinking", "Stop Thinking"),
    ]
    
    TITLE = "Thinking Widgets Test"
    
    def __init__(self):
        super().__init__()
        self.current_thinking: ThinkingWidget | None = None
        self.action_counter = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="test-container"):
            with Vertical(id="controls"):
                yield Static("Press 'T' for thinking widget, 'A' for action widget, 'S' to stop thinking")
                yield Button("Test Thinking Widget", id="test-thinking-btn")
                yield Button("Test Action Widget", id="test-action-btn")
            yield ScrollableContainer(id="widgets-area")
        yield Footer()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test-thinking-btn":
            await self.action_test_thinking()
        elif event.button.id == "test-action-btn":
            await self.action_test_action()
    
    async def action_test_thinking(self) -> None:
        """Test thinking widget functionality."""
        widgets_area = self.query_one("#widgets-area", ScrollableContainer)
        
        # Create thinking widget
        thinking = ThinkingWidget("Analyzing your complex request...")
        await widgets_area.mount(thinking)
        thinking.scroll_visible()
        thinking.start_thinking()
        
        self.current_thinking = thinking
        
        # Simulate thinking updates
        await asyncio.sleep(1)
        thinking.update_thinking_text("Processing data structures...")
        
        await asyncio.sleep(1)
        thinking.update_thinking_text("Evaluating multiple approaches...")
        
        await asyncio.sleep(1)
        thinking.update_thinking_text("Finalizing optimal solution...")
        
        # Set full thoughts for expansion
        full_thoughts = """Detailed thinking process:

1. First, I analyzed the user's request to understand the core requirements
2. Then I evaluated multiple possible approaches:
   - Direct implementation
   - Library-based solution
   - Custom algorithm
3. I considered performance implications and trade-offs
4. Finally, I selected the optimal approach based on maintainability and efficiency

This demonstrates the full thinking process that can be expanded by clicking."""
        
        thinking.set_full_thoughts(full_thoughts)
    
    async def action_test_action(self) -> None:
        """Test action widget functionality."""
        widgets_area = self.query_one("#widgets-area", ScrollableContainer)
        
        self.action_counter += 1
        
        # Create running action
        action = ActionWidget("tool_call", f"test_tool_{self.action_counter}", "running")
        action.set_parameters({"input": "test data", "option": "value"})
        
        await widgets_area.mount(action)
        action.scroll_visible()
        
        # Simulate action progression
        await asyncio.sleep(2)
        
        if self.action_counter % 3 == 0:
            # Simulate error
            action.set_error("Simulated tool execution error")
        else:
            # Simulate success
            result = f"Tool executed successfully! Result #{self.action_counter}"
            action.set_result(result)
    
    def action_stop_thinking(self) -> None:
        """Stop current thinking animation."""
        if self.current_thinking:
            self.current_thinking.stop_thinking()
            self.current_thinking.update_thinking_text("Thinking completed")
            self.current_thinking = None


async def main():
    """Run the thinking widgets test."""
    app = ThinkingTestApp()
    await app.run_async()


if __name__ == "__main__":
    print("🧠 Qwen-TUI Thinking Widgets Test")
    print("   Testing ThinkingWidget and ActionWidget components")
    print("   Controls:")
    print("   - T: Create thinking widget with animation")
    print("   - A: Create action widget (running → completed/error)")
    print("   - S: Stop current thinking animation")
    print("   - Click thinking widgets to expand/collapse")
    print("   - Ctrl+C: Exit")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔚 Test completed!")