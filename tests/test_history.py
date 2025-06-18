"""
Tests for conversation history functionality.
"""
import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime

from qwen_tui.history import ConversationHistory
from qwen_tui.config import Config


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config()


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for history files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def history_manager(config, temp_history_dir, monkeypatch):
    """Create a history manager with temporary directory."""
    # Mock the _get_history_directory method to use our temp directory
    def mock_get_history_dir(self):
        return temp_history_dir
    
    monkeypatch.setattr(ConversationHistory, "_get_history_directory", mock_get_history_dir)
    return ConversationHistory(config)


@pytest.mark.asyncio
async def test_session_creation(history_manager):
    """Test creating a new conversation session."""
    session_id = await history_manager.start_new_session()
    
    assert session_id is not None
    assert len(session_id) > 0
    assert history_manager.current_session_file is not None
    assert history_manager.current_session_file.exists()


@pytest.mark.asyncio
async def test_message_saving(history_manager):
    """Test saving messages to a session."""
    await history_manager.start_new_session()
    
    # Test saving a user message
    user_message = {"role": "user", "content": "Hello, test message"}
    await history_manager.save_message(user_message, "test_backend", "test_model")
    
    # Test saving an assistant message
    assistant_message = {"role": "assistant", "content": "Hello! How can I help you?"}
    await history_manager.save_message(assistant_message, "test_backend", "test_model")
    
    # Verify the file was updated
    assert history_manager.current_session_file.exists()
    
    with open(history_manager.current_session_file, 'r') as f:
        session_data = json.load(f)
    
    assert len(session_data["messages"]) == 2
    assert session_data["messages"][0]["role"] == "user"
    assert session_data["messages"][1]["role"] == "assistant"
    assert session_data["metadata"]["total_messages"] == 2
    assert session_data["metadata"]["backend_type"] == "test_backend"
    assert session_data["metadata"]["model"] == "test_model"


@pytest.mark.asyncio
async def test_session_loading(history_manager):
    """Test loading a conversation session."""
    # Create and populate a session
    session_id = await history_manager.start_new_session()
    
    test_messages = [
        {"role": "user", "content": "First message"},
        {"role": "assistant", "content": "First response"},
        {"role": "user", "content": "Second message"}
    ]
    
    for msg in test_messages:
        await history_manager.save_message(msg)
    
    # Load the session
    loaded_messages = await history_manager.load_session(session_id)
    
    assert loaded_messages is not None
    assert len(loaded_messages) == len(test_messages)
    
    for i, msg in enumerate(loaded_messages):
        assert msg["role"] == test_messages[i]["role"]
        assert msg["content"] == test_messages[i]["content"]
        # Timestamps should be removed from loaded messages
        assert "timestamp" not in msg


@pytest.mark.asyncio
async def test_recent_sessions(history_manager):
    """Test getting recent conversation sessions."""
    # Create multiple sessions
    session_ids = []
    for i in range(3):
        session_id = await history_manager.start_new_session()
        session_ids.append(session_id)
        
        # Add a message to each session
        await history_manager.save_message({
            "role": "user", 
            "content": f"Test message {i+1}"
        })
    
    # Get recent sessions
    recent_sessions = await history_manager.get_recent_sessions(limit=5)
    
    assert len(recent_sessions) >= 3  # At least our 3 sessions
    
    # Check session structure
    for session in recent_sessions:
        assert "session_id" in session
        assert "started_at" in session
        assert "message_count" in session
        assert "preview" in session
        assert session["message_count"] >= 0


@pytest.mark.asyncio
async def test_session_export_json(history_manager, temp_history_dir):
    """Test exporting a session to JSON format."""
    # Create and populate a session
    session_id = await history_manager.start_new_session()
    
    test_messages = [
        {"role": "user", "content": "Export test message"},
        {"role": "assistant", "content": "This will be exported"}
    ]
    
    for msg in test_messages:
        await history_manager.save_message(msg)
    
    # Export the session
    export_path = temp_history_dir / "exported_session.json"
    success = await history_manager.export_session(session_id, export_path, "json")
    
    assert success
    assert export_path.exists()
    
    # Verify exported content
    with open(export_path, 'r') as f:
        exported_data = json.load(f)
    
    assert "session_id" in exported_data
    assert "messages" in exported_data
    assert len(exported_data["messages"]) == 2


@pytest.mark.asyncio
async def test_session_export_txt(history_manager, temp_history_dir):
    """Test exporting a session to text format."""
    # Create and populate a session
    session_id = await history_manager.start_new_session()
    
    await history_manager.save_message({"role": "user", "content": "Hello"})
    await history_manager.save_message({"role": "assistant", "content": "Hi there!"})
    
    # Export the session
    export_path = temp_history_dir / "exported_session.txt"
    success = await history_manager.export_session(session_id, export_path, "txt")
    
    assert success
    assert export_path.exists()
    
    # Verify exported content
    with open(export_path, 'r') as f:
        content = f.read()
    
    assert "Conversation Session:" in content
    assert "User:" in content
    assert "Assistant:" in content
    assert "Hello" in content
    assert "Hi there!" in content


@pytest.mark.asyncio
async def test_session_deletion(history_manager):
    """Test deleting a conversation session."""
    # Create a session
    session_id = await history_manager.start_new_session()
    session_file = history_manager.current_session_file
    
    assert session_file.exists()
    
    # Delete the session
    success = await history_manager.delete_session(session_id)
    
    assert success
    assert not session_file.exists()


@pytest.mark.asyncio
async def test_cleanup_old_sessions(history_manager, temp_history_dir):
    """Test cleaning up old session files."""
    # Create a few sessions
    for i in range(3):
        await history_manager.start_new_session()
        await history_manager.save_message({"role": "user", "content": f"Message {i}"})
    
    # Get initial count
    session_files = list(temp_history_dir.glob("conversation_*.json"))
    initial_count = len(session_files)
    
    # Cleanup with 0 days (should delete everything older than current timestamp)
    # This won't delete our recent sessions, so let's create an old file manually
    old_session_file = temp_history_dir / "conversation_20200101_120000.json"
    old_session_file.write_text('{"session_id": "old", "messages": []}')
    
    deleted_count = await history_manager.cleanup_old_sessions(days_to_keep=1)
    
    # The old file should be deleted
    assert not old_session_file.exists()


@pytest.mark.asyncio
async def test_session_preview_generation(history_manager):
    """Test conversation preview generation."""
    session_id = await history_manager.start_new_session()
    
    # Test with user message
    await history_manager.save_message({
        "role": "user", 
        "content": "This is a long message that should be truncated when used as a preview because it exceeds the normal preview length limit"
    })
    
    sessions = await history_manager.get_recent_sessions(limit=1)
    assert len(sessions) == 1
    
    preview = sessions[0]["preview"]
    assert len(preview) <= 63  # Should be truncated
    assert "This is a long message" in preview


@pytest.mark.asyncio
async def test_invalid_session_operations(history_manager):
    """Test operations on invalid/non-existent sessions."""
    # Try to load non-existent session
    result = await history_manager.load_session("non_existent_session")
    assert result is None
    
    # Try to delete non-existent session
    success = await history_manager.delete_session("non_existent_session")
    assert not success
    
    # Try to export non-existent session
    export_path = Path("/tmp/test_export.json")
    success = await history_manager.export_session("non_existent_session", export_path)
    assert not success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])