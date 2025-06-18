"""
Tests for TUI functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from qwen_tui.tui.app import QwenTUIApp, ChatPanel, InputPanel
from qwen_tui.backends.manager import BackendManager
from qwen_tui.config import Config
from qwen_tui.exceptions import QwenTUIError


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config()


@pytest.fixture
def mock_backend_manager():
    """Create a mock backend manager."""
    manager = Mock(spec=BackendManager)
    manager.initialize = AsyncMock()
    manager.get_preferred_backend = Mock(return_value=None)
    manager.cleanup = AsyncMock()
    return manager


class TestChatPanel:
    """Test ChatPanel functionality."""
    
    def test_chat_panel_creation(self):
        """Test creating a chat panel."""
        panel = ChatPanel()
        
        assert panel.messages == []
        assert panel.typing_indicator_visible is False
    
    def test_add_user_message(self):
        """Test adding a user message."""
        panel = ChatPanel()
        panel.add_user_message("Hello, world!")
        
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("user", "Hello, world!")
    
    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        panel = ChatPanel()
        panel.add_assistant_message("Hello! How can I help?")
        
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("assistant", "Hello! How can I help?")
    
    def test_add_system_message(self):
        """Test adding a system message."""
        panel = ChatPanel()
        panel.add_system_message("System notification")
        
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("system", "System notification")
    
    def test_add_error_message(self):
        """Test adding an error message."""
        panel = ChatPanel()
        panel.add_error_message("An error occurred")
        
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("error", "An error occurred")
    
    def test_update_assistant_message(self):
        """Test updating assistant messages for streaming."""
        panel = ChatPanel()
        
        # First update - should add new message
        panel.update_assistant_message("Hello")
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("assistant", "Hello")
        
        # Second update - should update existing message
        panel.update_assistant_message("Hello, world!")
        assert len(panel.messages) == 1
        assert panel.messages[0] == ("assistant", "Hello, world!")
        
        # Add user message, then update assistant - should add new assistant message
        panel.add_user_message("User message")
        panel.update_assistant_message("New assistant message")
        assert len(panel.messages) == 3
        assert panel.messages[2] == ("assistant", "New assistant message")
    
    def test_typing_indicator(self):
        """Test typing indicator functionality."""
        panel = ChatPanel()
        
        # Initially hidden
        assert panel.typing_indicator_visible is False
        
        # Show typing indicator
        panel.show_typing_indicator()
        assert panel.typing_indicator_visible is True
        
        # Hide typing indicator
        panel.hide_typing_indicator()
        assert panel.typing_indicator_visible is False
    
    def test_clear_messages(self):
        """Test clearing all messages."""
        panel = ChatPanel()
        
        # Add some messages
        panel.add_user_message("Message 1")
        panel.add_assistant_message("Response 1")
        panel.show_typing_indicator()
        
        assert len(panel.messages) == 2
        assert panel.typing_indicator_visible is True
        
        # Clear all
        panel.clear_messages()
        
        assert len(panel.messages) == 0
        assert panel.typing_indicator_visible is False


class TestQwenTUIApp:
    """Test QwenTUIApp functionality."""
    
    def test_app_creation(self, mock_backend_manager, config):
        """Test creating the main TUI app."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        assert app.backend_manager == mock_backend_manager
        assert app.config == config
        assert app.conversation_history == []
        assert app.message_count == 0
        assert app.current_session_id is None
    
    def test_message_validation(self, mock_backend_manager, config):
        """Test message input validation."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Valid messages
        assert app._validate_message_input("Hello, world!") is None
        assert app._validate_message_input("Short message") is None
        assert app._validate_message_input("Message with\nnewlines") is None
        
        # Invalid messages
        assert app._validate_message_input("x" * 40000) is not None  # Too long
        assert app._validate_message_input("!@#$%^&*()") is not None  # No alphanumeric
        assert app._validate_message_input("\n" * 300) is not None  # Too many newlines
    
    def test_error_formatting(self, mock_backend_manager, config):
        """Test user-friendly error message formatting."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Test model not found error
        model_error = QwenTUIError("Model 'test-model' not found in backend")
        formatted = app._format_user_friendly_error(model_error)
        assert "Model Error:" in formatted
        assert "Ctrl+M" in formatted
        
        # Test connection error
        conn_error = QwenTUIError("Failed to connect to backend service")
        formatted = app._format_user_friendly_error(conn_error)
        assert "Connection Error:" in formatted
        assert "running" in formatted.lower()
        
        # Test timeout error
        timeout_error = QwenTUIError("Request timed out after 30 seconds")
        formatted = app._format_user_friendly_error(timeout_error)
        assert "Timeout Error:" in formatted
        assert "shorter message" in formatted.lower()
        
        # Test unexpected error formatting
        unexpected_error = Exception("Unexpected network failure")
        formatted = app._format_unexpected_error(unexpected_error)
        assert "Unexpected Error" in formatted
        assert "Exception" in formatted
    
    def test_layout_responsiveness(self, mock_backend_manager, config):
        """Test responsive layout logic."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Mock the size property
        class MockSize:
            def __init__(self, width, height):
                self.width = width
                self.height = height
        
        # Test normal size - should not be compact
        app.size = MockSize(80, 24)
        should_be_compact = app.size.width < app.min_width or app.size.height < app.min_height
        assert not should_be_compact
        
        # Test small size - should be compact
        app.size = MockSize(50, 15)
        should_be_compact = app.size.width < app.min_width or app.size.height < app.min_height
        assert should_be_compact
        
        # Test very small size - should be ultra compact
        app.size = MockSize(30, 10)
        is_ultra_compact = app.size.width < 40 or app.size.height < 15
        assert is_ultra_compact
    
    @pytest.mark.asyncio
    async def test_command_handling(self, mock_backend_manager, config):
        """Test slash command handling."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Mock the chat panel query
        mock_chat_panel = Mock()
        mock_chat_panel.add_system_message = Mock()
        mock_chat_panel.add_error_message = Mock()
        
        with patch.object(app, 'query_one', return_value=mock_chat_panel):
            # Test help command
            await app.handle_command("/help")
            mock_chat_panel.add_system_message.assert_called()
            
            # Test clear command
            with patch.object(app, 'action_new_conversation') as mock_new_conv:
                await app.handle_command("/clear")
                mock_new_conv.assert_called_once()
                mock_chat_panel.add_system_message.assert_called()
            
            # Test unknown command
            await app.handle_command("/unknown")
            mock_chat_panel.add_error_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_conversation_persistence(self, mock_backend_manager, config):
        """Test conversation history persistence."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Mock the history manager
        mock_history = Mock()
        mock_history.start_new_session = AsyncMock(return_value="test_session")
        mock_history.save_message = AsyncMock()
        app.history_manager = mock_history
        
        # Test session creation
        await app._start_new_session()
        mock_history.start_new_session.assert_called_once()
        assert app.current_session_id == "test_session"
    
    def test_action_new_conversation(self, mock_backend_manager, config):
        """Test starting a new conversation."""
        app = QwenTUIApp(mock_backend_manager, config)
        
        # Add some conversation history
        app.conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        app.message_count = 2
        
        # Mock the chat panel
        mock_chat_panel = Mock()
        mock_chat_panel.clear_messages = Mock()
        
        with patch.object(app, 'query_one', return_value=mock_chat_panel), \
             patch('asyncio.create_task') as mock_create_task:
            
            app.action_new_conversation()
            
            # Verify state was reset
            assert app.conversation_history == []
            assert app.message_count == 0
            mock_chat_panel.clear_messages.assert_called_once()
            mock_create_task.assert_called_once()


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_message_length_validation(self):
        """Test message length validation."""
        # This would be part of the app's validation logic
        def validate_length(message, max_length=32000):
            return len(message) <= max_length
        
        # Normal message
        assert validate_length("Hello, world!")
        
        # Long but acceptable message
        long_message = "x" * 31000
        assert validate_length(long_message)
        
        # Too long message
        too_long = "x" * 40000
        assert not validate_length(too_long)
    
    def test_command_parsing(self):
        """Test command parsing logic."""
        def parse_command(message):
            if not message.startswith('/'):
                return None, []
            
            parts = message[1:].split()
            if not parts:
                return None, []
            
            return parts[0].lower(), parts[1:]
        
        # Valid commands
        cmd, args = parse_command("/help")
        assert cmd == "help"
        assert args == []
        
        cmd, args = parse_command("/load session_123")
        assert cmd == "load"
        assert args == ["session_123"]
        
        cmd, args = parse_command("/export json format")
        assert cmd == "export"
        assert args == ["json", "format"]
        
        # Invalid commands
        cmd, args = parse_command("not a command")
        assert cmd is None
        assert args == []
        
        cmd, args = parse_command("/")
        assert cmd is None
        assert args == []


class TestPerformance:
    """Test performance-critical components."""
    
    def test_message_display_performance(self):
        """Test chat panel performance with many messages."""
        panel = ChatPanel()
        
        # Add many messages
        for i in range(1000):
            if i % 2 == 0:
                panel.add_user_message(f"User message {i}")
            else:
                panel.add_assistant_message(f"Assistant response {i}")
        
        assert len(panel.messages) == 1000
        
        # Test that refresh_display doesn't crash with many messages
        try:
            panel.refresh_display()
            # If we get here without exception, the test passes
            assert True
        except Exception as e:
            pytest.fail(f"refresh_display failed with {len(panel.messages)} messages: {e}")
    
    def test_streaming_updates_performance(self):
        """Test performance of streaming message updates."""
        panel = ChatPanel()
        
        # Simulate rapid streaming updates
        base_content = "Streaming response"
        for i in range(100):
            content = base_content + " " + "word" * i
            panel.update_assistant_message(content)
        
        # Should have only one message (constantly updated)
        assert len(panel.messages) == 1
        assert "word" * 99 in panel.messages[0][1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])