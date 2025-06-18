#!/usr/bin/env python3
"""
Simple test for thinking widget functionality.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from qwen_tui.tui.app import ThinkingWidget, ActionWidget

def test_thinking_widget():
    """Test ThinkingWidget functionality."""
    print("🧠 Testing ThinkingWidget...")
    
    # Create widget
    widget = ThinkingWidget("Initial thinking text")
    print("✅ ThinkingWidget created")
    
    # Test thinking text updates
    widget.update_thinking_text("Updated thinking text")
    print("✅ Thinking text updated")
    
    # Test full thoughts
    widget.set_full_thoughts("This is the full thought process with detailed reasoning...")
    print("✅ Full thoughts set")
    
    # Test expansion toggle
    widget.toggle_expansion()
    print("✅ Expansion toggled")
    
    print("✅ ThinkingWidget tests passed")

def test_action_widget():
    """Test ActionWidget functionality."""
    print("🔧 Testing ActionWidget...")
    
    # Create widget
    widget = ActionWidget("tool_call", "test_tool", "running")
    print("✅ ActionWidget created")
    
    # Test parameters
    widget.set_parameters({"param1": "value1", "param2": "value2"})
    print("✅ Parameters set")
    
    # Test result
    widget.set_result("Tool execution completed successfully")
    print("✅ Result set")
    
    # Test error
    error_widget = ActionWidget("tool_call", "error_tool", "running")
    error_widget.set_error("Simulated error")
    print("✅ Error set")
    
    print("✅ ActionWidget tests passed")

def main():
    print("🧪 Simple Thinking Widgets Test")
    print("="*50)
    
    try:
        test_thinking_widget()
        print()
        test_action_widget()
        print()
        print("🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()