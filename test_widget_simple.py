#!/usr/bin/env python3
"""
Simple test to verify widget rendering without terminal issues.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from qwen_tui.tui.app import ThinkingWidget, ActionWidget

# Test creating widgets without rich markup
thinking = ThinkingWidget("Test thinking process")
print("ThinkingWidget created successfully")

# Test the update methods
thinking.update_thinking_text("Analyzing the problem...")
print("ThinkingWidget text updated")

# Test ActionWidget
action = ActionWidget("tool_call", "test_tool")
action.set_parameters({"test": "param"})
action.set_result("Test completed")
print("ActionWidget created and updated successfully")

print("✅ All widget operations completed without errors")