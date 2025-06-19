#!/usr/bin/env python3
"""
Test script to verify input panel layout is working correctly.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button
from textual.binding import Binding

from qwen_tui.tui.app import InputPanel


class InputLayoutTestApp(App):
    """Test app for input panel layout."""
    
    CSS_PATH = Path(__file__).parent / "src" / "qwen_tui" / "tui" / "styles.css"
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("1", "test_normal", "Normal"),
        Binding("2", "test_compact", "Compact"),
        Binding("3", "test_ultra", "Ultra Compact"),
    ]
    
    TITLE = "Input Layout Test"
    
    def __init__(self):
        super().__init__()
        self.layout_mode = "normal"
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="test-container"):
            yield Static("Input Panel Layout Test", id="title")
            yield Static("Press 1/2/3 to test different layout modes", id="instructions")
            yield Static("", id="status")
            yield ScrollableContainer(
                Static("This is the chat area where messages would appear."),
                Static("The input panel below should maintain proper proportions."),
                Static("Type messages to test the input functionality."),
                id="chat-scroll"
            )
            yield InputPanel(id="input-panel")
        yield Footer()
    
    def on_mount(self) -> None:
        self.update_status()
    
    def update_status(self) -> None:
        status = self.query_one("#status", Static)
        status.update(f"Current layout mode: {self.layout_mode}")
        
        # Apply layout classes
        if self.layout_mode == "compact":
            self.add_class("compact-layout")
            self.remove_class("ultra-compact")
        elif self.layout_mode == "ultra":
            self.add_class("ultra-compact")
            self.remove_class("compact-layout")
        else:
            self.remove_class("compact-layout")
            self.remove_class("ultra-compact")
    
    def action_test_normal(self) -> None:
        self.layout_mode = "normal"
        self.update_status()
    
    def action_test_compact(self) -> None:
        self.layout_mode = "compact"
        self.update_status()
    
    def action_test_ultra(self) -> None:
        self.layout_mode = "ultra"
        self.update_status()


async def main():
    """Run the input layout test."""
    app = InputLayoutTestApp()
    await app.run_async()


if __name__ == "__main__":
    print("🧪 Input Panel Layout Test")
    print("   Testing input panel responsiveness and layout")
    print("   Controls:")
    print("   - 1: Normal layout")
    print("   - 2: Compact layout") 
    print("   - 3: Ultra compact layout")
    print("   - Type messages to test input functionality")
    print("   - Ctrl+C: Exit")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔚 Layout test completed!")