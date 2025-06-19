import pytest
pytest.skip("manual test", allow_module_level=True)
#!/usr/bin/env python3
"""
Comprehensive test for the full thinking system integration.

Tests the complete flow from user message to thinking process to response.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button
from textual.binding import Binding

from qwen_tui.backends.manager import BackendManager
from qwen_tui.config import Config
from qwen_tui.tui.app import QwenTUIApp, ThinkingWidget, ActionWidget


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
    
    #test-area {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    #input-area {
        height: auto;
        margin-top: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("1", "test_calculation", "Test Calc"),
        Binding("2", "test_analysis", "Test Analysis"),
        Binding("3", "test_search", "Test Search"),
    ]
    
    TITLE = "Full Thinking System Test"
    
    def __init__(self):\n        super().__init__()\n        self.test_counter = 0\n    \n    def compose(self) -> ComposeResult:\n        yield Header()\n        with Vertical(id=\"test-container\"):\n            with Vertical(id=\"controls\"):\n                yield Static(\"Thinking System Integration Test\")\n                yield Static(\"Press 1/2/3 for different test scenarios, or type custom message\")\n            yield ScrollableContainer(id=\"test-area\")\n            with Vertical(id=\"input-area\"):\n                yield Input(placeholder=\"Type a message to test thinking system...\", id=\"test-input\")\n                yield Button(\"Send Test Message\", id=\"send-btn\")\n        yield Footer()\n    \n    async def on_input_submitted(self, event: Input.Submitted) -> None:\n        \"\"\"Handle input submission.\"\"\"\n        await self.process_test_message(event.value)\n        event.input.value = \"\"\n    \n    async def on_button_pressed(self, event: Button.Pressed) -> None:\n        if event.button.id == \"send-btn\":\n            input_widget = self.query_one(\"#test-input\", Input)\n            await self.process_test_message(input_widget.value)\n            input_widget.value = \"\"\n    \n    async def action_test_calculation(self) -> None:\n        \"\"\"Test calculation scenario.\"\"\"\n        await self.process_test_message(\"Calculate 15 * 23 + 45\")\n    \n    async def action_test_analysis(self) -> None:\n        \"\"\"Test text analysis scenario.\"\"\"\n        await self.process_test_message(\"Please analyze this text for sentiment and clarity\")\n    \n    async def action_test_search(self) -> None:\n        \"\"\"Test search scenario.\"\"\"\n        await self.process_test_message(\"Search for information about Python async programming\")\n    \n    async def process_test_message(self, message: str) -> None:\n        \"\"\"Process a test message through the thinking system.\"\"\"\n        if not message.strip():\n            return\n        \n        test_area = self.query_one(\"#test-area\", ScrollableContainer)\n        self.test_counter += 1\n        \n        # Add user message\n        user_msg = Static(f\"[bold blue]User #{self.test_counter}:[/bold blue] {message}\")\n        await test_area.mount(user_msg)\n        user_msg.scroll_visible()\n        \n        # Create thinking widget\n        thinking_widget = ThinkingWidget(\"Processing your request...\")\n        await test_area.mount(thinking_widget)\n        thinking_widget.scroll_visible()\n        thinking_widget.start_thinking()\n        \n        # Simulate thinking process\n        await asyncio.sleep(1)\n        thinking_widget.update_thinking_text(\"Analyzing message content...\")\n        \n        await asyncio.sleep(1)\n        thinking_widget.update_thinking_text(\"Determining required tools...\")\n        \n        # Simulate tool usage based on message\n        if any(word in message.lower() for word in ['calculate', 'math', '+', '-', '*', '/']):\n            action_widget = ActionWidget(\"tool_call\", \"calculator\", \"running\")\n            action_widget.set_parameters({\"expression\": \"extracted from message\"})\n            await test_area.mount(action_widget)\n            action_widget.scroll_visible()\n            \n            await asyncio.sleep(2)\n            action_widget.set_result(\"Calculation completed: 390\")\n            \n        elif any(word in message.lower() for word in ['analyze', 'sentiment', 'text']):\n            action_widget = ActionWidget(\"tool_call\", \"text_analyzer\", \"running\")\n            action_widget.set_parameters({\"text\": message[:30] + \"...\"})\n            await test_area.mount(action_widget)\n            action_widget.scroll_visible()\n            \n            await asyncio.sleep(2)\n            action_widget.set_result(\"Analysis: Neutral sentiment, clear intent\")\n            \n        elif any(word in message.lower() for word in ['search', 'find', 'information']):\n            action_widget = ActionWidget(\"tool_call\", \"web_search\", \"running\")\n            action_widget.set_parameters({\"query\": \"Python async programming\"})\n            await test_area.mount(action_widget)\n            action_widget.scroll_visible()\n            \n            await asyncio.sleep(2.5)\n            action_widget.set_result(\"Found 5 relevant articles and tutorials\")\n        \n        # Complete thinking\n        await asyncio.sleep(1)\n        thinking_widget.stop_thinking()\n        thinking_widget.update_thinking_text(\"Synthesis complete - ready to respond\")\n        \n        full_thoughts = f\"\"\"Detailed thinking process for: \"{message}\"\n\n1. Parsed the user's request to understand intent\n2. Identified key components and requirements\n3. Selected appropriate tools for the task\n4. Executed tool calls with relevant parameters\n5. Synthesized results into comprehensive response\n\nThis demonstrates the full thinking system working end-to-end!\"\"\"\n        \n        thinking_widget.set_full_thoughts(full_thoughts)\n        \n        # Add final response\n        response_msg = Static(f\"[bold green]Assistant:[/bold green] I've processed your request using the thinking system! The tools executed successfully and I can see the complete thought process. Click the thinking widget above to see the full details.\")\n        await test_area.mount(response_msg)\n        response_msg.scroll_visible()\n        \n        # Add separator\n        separator = Static(\"[dim]\" + \"─\" * 60 + \"[/dim]\")\n        await test_area.mount(separator)\n        separator.scroll_visible()\n\n\nasync def main():\n    \"\"\"Run the full thinking system test.\"\"\"\n    app = ThinkingSystemTestApp()\n    await app.run_async()\n\n\nif __name__ == \"__main__\":\n    print(\"🧠 Full Thinking System Test\")\n    print(\"   Testing complete integration from message to response\")\n    print(\"   Test scenarios:\")\n    print(\"   - Press 1: Test calculation (triggers calculator tool)\")\n    print(\"   - Press 2: Test analysis (triggers text analyzer tool)\")\n    print(\"   - Press 3: Test search (triggers web search tool)\")\n    print(\"   - Type custom messages to test different scenarios\")\n    print(\"   - Click thinking widgets to expand full thought process\")\n    print(\"   - Ctrl+C: Exit\")\n    print()\n    \n    try:\n        asyncio.run(main())\n    except KeyboardInterrupt:\n        print(\"\\n🔚 Thinking system test completed!\")