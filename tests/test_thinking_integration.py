#!/usr/bin/env python3
"""
Integration test to verify thinking tags are properly hidden in the TUI.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncio
from qwen_tui.tui.app import ThinkingWidget, ChatMessage

async def test_thinking_integration():
    """Test that thinking tags are properly filtered in the complete system."""
    print("🧪 Testing Thinking Integration")
    print("=" * 50)
    
    # Simulate a response that contains thinking tags
    mock_llm_response = """<think>
The user wants me to calculate something. Let me think through this:
1. I need to identify what they're asking for
2. Break down the calculation steps
3. Provide a clear answer
</think>

I'll help you with that calculation!

<think>
Actually, let me double-check my math here:
- First step: 15 * 23 = 345
- Second step: 345 + 45 = 390
Yes, that's correct.
</think>

The result of 15 × 23 + 45 is **390**.

Here's how I calculated it:
1. 15 × 23 = 345
2. 345 + 45 = 390"""
    
    # Test the filtering function
    from qwen_tui.tui.thinking import ThinkingManager
    from qwen_tui.backends.manager import BackendManager
    from qwen_tui.config import Config
    
    config = Config()
    backend_manager = BackendManager(config)
    manager = ThinkingManager(backend_manager, config)
    
    visible_content, thinking_content = manager._filter_thinking_tags(mock_llm_response)
    
    print("📝 Mock LLM Response (with thinking tags):")
    print(repr(mock_llm_response))
    print("\n🔍 Extracted Thinking Content:")
    print(repr(thinking_content))
    print("\n👀 Visible Content (what user sees):")
    print(repr(visible_content))
    
    # Verify thinking content was extracted
    expected_thinking_parts = [
        "The user wants me to calculate something",
        "Actually, let me double-check my math here"
    ]
    
    thinking_success = all(part in thinking_content for part in expected_thinking_parts)
    
    # Verify thinking tags were removed from visible content
    visible_success = "<think>" not in visible_content and "</think>" not in visible_content
    
    # Verify visible content contains the expected response
    content_success = "The result of 15 × 23 + 45 is **390**" in visible_content
    
    print(f"\n📊 Test Results:")
    print(f"  ✅ Thinking content extracted: {thinking_success}")
    print(f"  ✅ Thinking tags removed from visible: {visible_success}")
    print(f"  ✅ Visible content preserved: {content_success}")
    
    overall_success = thinking_success and visible_success and content_success
    
    if overall_success:
        print(f"\n🎉 Integration test PASSED!")
        print("   The thinking system correctly:")
        print("   - Extracts internal reasoning from <think> tags")
        print("   - Hides thinking tags from user")
        print("   - Preserves the actual response content")
    else:
        print(f"\n❌ Integration test FAILED!")
        print("   There are issues with thinking tag processing")
    
    return overall_success

if __name__ == "__main__":
    success = asyncio.run(test_thinking_integration())
    sys.exit(0 if success else 1)