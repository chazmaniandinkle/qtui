#!/usr/bin/env python3
"""
Test script for thinking tag filtering functionality.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_thinking_filter():
    """Test the thinking tag filtering function."""
    # Import the filter function
    from qwen_tui.tui.thinking import ThinkingManager
    from qwen_tui.backends.manager import BackendManager
    from qwen_tui.config import Config
    
    # Create a dummy thinking manager to test the filter method
    config = Config()
    backend_manager = BackendManager(config)
    manager = ThinkingManager(backend_manager, config)
    
    # Test cases
    test_cases = [
        # Basic thinking tag
        {
            'input': '<think>I need to calculate this</think>The answer is 42.',
            'expected_visible': 'The answer is 42.',
            'expected_thinking': 'I need to calculate this'
        },
        # Multiple thinking tags
        {
            'input': '<think>First thought</think>Some text<think>Second thought</think>More text',
            'expected_visible': 'Some text\n\nMore text',
            'expected_thinking': 'First thought\nSecond thought'
        },
        # No thinking tags
        {
            'input': 'Just regular content without thinking tags.',
            'expected_visible': 'Just regular content without thinking tags.',
            'expected_thinking': ''
        },
        # Multiline thinking
        {
            'input': '<think>This is a\nmultiline thinking\nprocess</think>Final answer here.',
            'expected_visible': 'Final answer here.',
            'expected_thinking': 'This is a\nmultiline thinking\nprocess'
        },
        # Case insensitive
        {
            'input': '<THINK>Uppercase tags</THINK>Result text',
            'expected_visible': 'Result text',
            'expected_thinking': 'Uppercase tags'
        },
        # Mixed case
        {
            'input': '<Think>Mixed case</Think>Output here',
            'expected_visible': 'Output here',
            'expected_thinking': 'Mixed case'
        }
    ]
    
    print("🧪 Testing Thinking Tag Filter")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        visible, thinking = manager._filter_thinking_tags(test_case['input'])
        
        print(f"\nTest {i}:")
        print(f"  Input: {repr(test_case['input'])}")
        print(f"  Expected visible: {repr(test_case['expected_visible'])}")
        print(f"  Actual visible: {repr(visible)}")
        print(f"  Expected thinking: {repr(test_case['expected_thinking'])}")
        print(f"  Actual thinking: {repr(thinking)}")
        
        if visible == test_case['expected_visible'] and thinking == test_case['expected_thinking']:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Thinking tag filtering is working correctly.")
    else:
        print("⚠️ Some tests failed. There may be issues with the filtering logic.")
    
    return failed == 0

if __name__ == "__main__":
    test_thinking_filter()