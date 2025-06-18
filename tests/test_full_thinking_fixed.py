#!/usr/bin/env python3
"""
Comprehensive test for the full thinking system integration.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button
from textual.binding import Binding

from qwen_tui.tui.app import ThinkingWidget, ActionWidget


class ThinkingSystemTestApp(App):
    """Test app for the full thinking system."""
    
    CSS = """
    .thinking-widget {
        background: $surface;
        border-left: solid $warning;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
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
    
    #test-area {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("1", "test_calculation", "Test Calc"),
        Binding("2", "test_analysis", "Test Analysis"),
        Binding("3", "test_search", "Test Search"),
    ]
    
    TITLE = "Full Thinking System Test"
    
    def __init__(self):
        super().__init__()
        self.test_counter = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="test-container"):
            yield Static("Thinking System Integration Test")
            yield Static("Press 1/2/3 for test scenarios, or type custom message")
            yield ScrollableContainer(id="test-area")
            yield Input(placeholder="Type message...", id="test-input")
            yield Button("Send", id="send-btn")
        yield Footer()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.process_test_message(event.value)
        event.input.value = ""
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            input_widget = self.query_one("#test-input", Input)
            await self.process_test_message(input_widget.value)
            input_widget.value = ""
    
    async def action_test_calculation(self) -> None:
        await self.process_test_message("Calculate 15 * 23 + 45")
    
    async def action_test_analysis(self) -> None:
        await self.process_test_message("Please analyze this text for sentiment")
    
    async def action_test_search(self) -> None:
        await self.process_test_message("Search for Python async programming info")
    
    async def process_test_message(self, message: str) -> None:
        if not message.strip():
            return
        
        test_area = self.query_one("#test-area", ScrollableContainer)
        self.test_counter += 1
        
        # Add user message
        user_msg = Static(f"[bold blue]User #{self.test_counter}:[/bold blue] {message}")
        await test_area.mount(user_msg)
        user_msg.scroll_visible()
        
        # Create thinking widget
        thinking_widget = ThinkingWidget("Processing your request...")
        await test_area.mount(thinking_widget)
        thinking_widget.scroll_visible()
        thinking_widget.start_thinking()
        
        # Simulate thinking process
        await asyncio.sleep(1)
        thinking_widget.update_thinking_text("Analyzing message content...")
        
        await asyncio.sleep(1)
        thinking_widget.update_thinking_text("Determining required tools...")
        
        # Simulate tool usage
        if any(word in message.lower() for word in ['calculate', 'math', '+', '-', '*', '/']):
            action_widget = ActionWidget("tool_call", "calculator", "running")
            action_widget.set_parameters({"expression": "15 * 23 + 45"})
            await test_area.mount(action_widget)
            action_widget.scroll_visible()
            
            await asyncio.sleep(2)
            action_widget.set_result("390")
            
        elif any(word in message.lower() for word in ['analyze', 'sentiment', 'text']):
            action_widget = ActionWidget("tool_call", "text_analyzer", "running")
            action_widget.set_parameters({"text": message[:30] + "..."})
            await test_area.mount(action_widget)
            action_widget.scroll_visible()
            
            await asyncio.sleep(2)
            action_widget.set_result("Neutral sentiment, clear intent")
            
        elif any(word in message.lower() for word in ['search', 'find', 'information']):
            action_widget = ActionWidget("tool_call", "web_search", "running")
            action_widget.set_parameters({"query": "Python async programming"})
            await test_area.mount(action_widget)
            action_widget.scroll_visible()
            
            await asyncio.sleep(2.5)
            action_widget.set_result("Found 5 relevant articles")
        
        # Complete thinking
        await asyncio.sleep(1)
        thinking_widget.stop_thinking()
        thinking_widget.update_thinking_text("Synthesis complete")
        
        full_thoughts = f"""Detailed thinking for: "{message}"

1. Parsed user request
2. Identified key components  
3. Selected appropriate tools
4. Executed tool calls
5. Synthesized results

Complete thinking system demonstration!"""
        
        thinking_widget.set_full_thoughts(full_thoughts)
        
        # Add response
        response_msg = Static("[bold green]Assistant:[/bold green] Request processed with thinking system! Click thinking widget to see details.")
        await test_area.mount(response_msg)
        response_msg.scroll_visible()
        
        # Add separator
        separator = Static("[dim]" + "─" * 60 + "[/dim]")
        await test_area.mount(separator)
        separator.scroll_visible()


async def main():
    app = ThinkingSystemTestApp()
    await app.run_async()


if __name__ == "__main__":
    print("🧠 Full Thinking System Test")
    print("   Press 1: Test calculation")
    print("   Press 2: Test analysis") 
    print("   Press 3: Test search")
    print("   Type custom messages")
    print("   Click thinking widgets to expand")
    print("   Ctrl+C: Exit")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔚 Thinking system test completed!")