#!/usr/bin/env python3
"""
Qwen-TUI Layout Testing Tool

This script provides various testing modes for the TUI to help visualize 
and troubleshoot layout issues, responsive design, and functionality.
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add src to path so we can import qwen_tui
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qwen_tui.config import Config
from qwen_tui.backends.manager import BackendManager
from qwen_tui.tui.app import QwenTUIApp


class TUITester:
    """TUI testing utility class."""
    
    def __init__(self, test_duration: int = 5):
        self.test_duration = test_duration
        self.config = Config()
        self.backend_manager = None
        self.app = None
    
    async def setup(self):
        """Initialize the TUI components."""
        print(f"🔧 Setting up TUI test environment...")
        self.backend_manager = BackendManager(self.config)
        self.app = QwenTUIApp(self.backend_manager, self.config)
        print(f"✅ TUI components initialized")
    
    async def test_basic_startup(self):
        """Test basic TUI startup and shutdown."""
        print(f"🚀 Testing basic TUI startup...")
        
        async def auto_exit():
            await asyncio.sleep(self.test_duration)
            print(f"⏰ Auto-exiting after {self.test_duration} seconds")
            self.app.exit()
        
        # Start auto-exit task
        asyncio.create_task(auto_exit())
        
        # Run the app
        await self.app.run_async()
        print("✅ Basic startup test completed")
    
    async def test_responsive_design(self):
        """Test responsive design by simulating different screen sizes."""
        print(f"📱 Testing responsive design...")
        
        # Test different scenarios
        test_scenarios = [
            ("Normal layout", 80, 24, 3),
            ("Compact layout", 50, 20, 3), 
            ("Ultra-compact layout", 35, 15, 3),
            ("Minimal layout", 30, 12, 2),
        ]
        
        for name, width, height, duration in test_scenarios:
            print(f"  🔍 Testing {name} ({width}x{height})...")
            
            async def test_scenario():
                await asyncio.sleep(0.5)  # Allow initialization
                
                # Simulate terminal resize
                self.app.size = self.app.size.__class__(width, height)
                self.app.check_layout()
                
                # Add test messages to visualize layout
                self.app.add_system_message(f"Testing {name}")
                self.app.add_system_message(f"Screen size: {width}x{height}")
                self.app.add_system_message("Type a message to test input...")
                
                await asyncio.sleep(duration)
                
                if name != test_scenarios[-1][0]:  # Not the last test
                    self.app.clear_chat()
            
            asyncio.create_task(test_scenario())
        
        # Auto-exit after all tests
        async def auto_exit():
            total_duration = sum(s[3] for s in test_scenarios) + 1
            await asyncio.sleep(total_duration)
            print(f"⏰ Responsive design test completed")
            self.app.exit()
        
        asyncio.create_task(auto_exit())
        await self.app.run_async()
        print("✅ Responsive design test completed")
    
    async def test_interactive_mode(self):
        """Run TUI in interactive mode for manual testing."""
        print(f"🎮 Starting interactive TUI mode...")
        print(f"   Press Ctrl+C to exit")
        print(f"   Try different key combinations:")
        print(f"   - Ctrl+M: Model selector")
        print(f"   - Ctrl+N: New conversation")
        print(f"   - Ctrl+H: Help")
        print(f"   - /help: Show help commands")
        
        # Add some test content
        await asyncio.sleep(0.5)
        self.app.add_system_message("🎮 Interactive TUI Test Mode")
        self.app.add_system_message("Try typing messages, using shortcuts, and testing the interface")
        self.app.add_system_message("Available slash commands: /help, /models, /backends, /history")
        
        try:
            await self.app.run_async()
        except KeyboardInterrupt:
            print("\n✅ Interactive test session ended")
    
    async def test_layout_stress(self):
        """Stress test the layout with many messages."""
        print(f"💪 Testing layout stress with multiple messages...")
        
        async def stress_test():
            await asyncio.sleep(0.5)  # Allow initialization
            
            # Add many messages to test scrolling
            self.app.add_system_message("🔥 Layout Stress Test Starting...")
            
            for i in range(20):
                if i % 4 == 0:
                    self.app.add_system_message(f"System message #{i+1}: Testing scrolling behavior")
                elif i % 4 == 1:
                    # Simulate user message
                    from qwen_tui.tui.app import ChatMessage
                    chat_scroll = self.app.query_one("#chat-scroll")
                    user_msg = ChatMessage("user", f"User message #{i+1}: How does the layout handle long messages?")
                    await chat_scroll.mount(user_msg)
                    user_msg.scroll_visible()
                elif i % 4 == 2:
                    # Simulate assistant message
                    from qwen_tui.tui.app import ChatMessage
                    chat_scroll = self.app.query_one("#chat-scroll")
                    assistant_msg = ChatMessage("assistant", f"Assistant response #{i+1}: This is a response that tests how the TUI handles multiple lines and formatting. The layout should remain stable and readable even with many messages.")
                    await chat_scroll.mount(assistant_msg)
                    assistant_msg.scroll_visible()
                else:
                    self.app.add_error_message(f"Error message #{i+1}: Testing error display")
                
                await asyncio.sleep(0.2)  # Small delay between messages
            
            self.app.add_system_message("✅ Stress test completed - scroll to see all messages")
            
            await asyncio.sleep(self.test_duration)
            self.app.exit()
        
        asyncio.create_task(stress_test())
        await self.app.run_async()
        print("✅ Layout stress test completed")


async def run_test_mode(mode: str, duration: int):
    """Run the specified test mode."""
    tester = TUITester(test_duration=duration)
    await tester.setup()
    
    if mode == "basic":
        await tester.test_basic_startup()
    elif mode == "responsive":
        await tester.test_responsive_design()
    elif mode == "interactive":
        await tester.test_interactive_mode()
    elif mode == "stress":
        await tester.test_layout_stress()
    else:
        print(f"❌ Unknown test mode: {mode}")
        return False
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Qwen-TUI Layout Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Modes:
  basic        Basic startup/shutdown test (default)
  responsive   Test responsive design with different screen sizes
  interactive  Interactive mode for manual testing (no timeout)
  stress       Stress test with many messages

Examples:
  python test_tui_layout.py                    # Basic test (5 seconds)
  python test_tui_layout.py -m responsive     # Test responsive design
  python test_tui_layout.py -m interactive    # Interactive mode
  python test_tui_layout.py -m stress -d 10   # Stress test for 10 seconds
        """
    )
    
    parser.add_argument(
        "-m", "--mode",
        choices=["basic", "responsive", "interactive", "stress"],
        default="basic",
        help="Test mode to run (default: basic)"
    )
    
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=5,
        help="Test duration in seconds (default: 5, ignored for interactive mode)"
    )
    
    args = parser.parse_args()
    
    print(f"🧪 Qwen-TUI Layout Testing Tool")
    print(f"   Mode: {args.mode}")
    if args.mode != "interactive":
        print(f"   Duration: {args.duration} seconds")
    print()
    
    try:
        result = asyncio.run(run_test_mode(args.mode, args.duration))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()