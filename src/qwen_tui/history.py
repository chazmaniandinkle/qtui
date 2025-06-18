"""
Conversation history persistence for Qwen-TUI.

Provides functionality to save and load conversation history between sessions.
"""
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiofiles

from .config import Config
from .logging import get_main_logger


class ConversationHistory:
    """Manages conversation history persistence."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_main_logger()
        self.history_dir = self._get_history_directory()
        self.current_session_file: Optional[Path] = None
        
    def _get_history_directory(self) -> Path:
        """Get the directory for storing conversation history."""
        import os
        
        # Use XDG_DATA_HOME or fallback to ~/.local/share
        if data_home := os.getenv("XDG_DATA_HOME"):
            data_dir = Path(data_home) / "qwen-tui"
        else:
            data_dir = Path.home() / ".local" / "share" / "qwen-tui"
        
        history_dir = data_dir / "conversations"
        history_dir.mkdir(parents=True, exist_ok=True)
        return history_dir
    
    def _generate_session_filename(self) -> str:
        """Generate a unique filename for the current session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"conversation_{timestamp}.json"
    
    async def start_new_session(self) -> str:
        """Start a new conversation session and return session ID."""
        filename = self._generate_session_filename()
        self.current_session_file = self.history_dir / filename
        
        # Create initial session file
        session_data = {
            "session_id": filename[:-5],  # Remove .json extension
            "started_at": datetime.now().isoformat(),
            "messages": [],
            "metadata": {
                "backend_type": None,
                "model": None,
                "total_messages": 0
            }
        }
        
        try:
            async with aiofiles.open(self.current_session_file, 'w') as f:
                await f.write(json.dumps(session_data, indent=2))
            
            self.logger.info("Started new conversation session", 
                           session_id=session_data["session_id"])
            return session_data["session_id"]
            
        except Exception as e:
            self.logger.error("Failed to create session file", error=str(e))
            return ""
    
    async def save_message(self, message: Dict[str, Any], backend_type: Optional[str] = None, model: Optional[str] = None) -> None:
        """Save a message to the current session."""
        if not self.current_session_file or not self.current_session_file.exists():
            await self.start_new_session()
        
        try:
            # Read current session data
            async with aiofiles.open(self.current_session_file, 'r') as f:
                content = await f.read()
                session_data = json.loads(content)
            
            # Add timestamp to message
            message_with_timestamp = {
                **message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add message to session
            session_data["messages"].append(message_with_timestamp)
            session_data["metadata"]["total_messages"] = len(session_data["messages"])
            
            # Update metadata if provided
            if backend_type:
                session_data["metadata"]["backend_type"] = backend_type
            if model:
                session_data["metadata"]["model"] = model
            
            # Save updated session
            async with aiofiles.open(self.current_session_file, 'w') as f:
                await f.write(json.dumps(session_data, indent=2))
                
        except Exception as e:
            self.logger.error("Failed to save message to session", error=str(e))
    
    async def load_session(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load conversation history from a specific session."""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            self.logger.warning("Session file not found", session_id=session_id)
            return None
        
        try:
            async with aiofiles.open(session_file, 'r') as f:
                content = await f.read()
                session_data = json.loads(content)
            
            # Extract messages without timestamps for conversation history
            messages = []
            for msg in session_data.get("messages", []):
                # Remove timestamp from message for conversation history
                clean_msg = {k: v for k, v in msg.items() if k != "timestamp"}
                messages.append(clean_msg)
            
            self.logger.info("Loaded conversation session", 
                           session_id=session_id,
                           message_count=len(messages))
            return messages
            
        except Exception as e:
            self.logger.error("Failed to load session", session_id=session_id, error=str(e))
            return None
    
    async def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get a list of recent conversation sessions."""
        try:
            session_files = list(self.history_dir.glob("conversation_*.json"))
            session_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            sessions = []
            for session_file in session_files[:limit]:
                try:
                    async with aiofiles.open(session_file, 'r') as f:
                        content = await f.read()
                        session_data = json.loads(content)
                    
                    # Extract summary info
                    metadata = session_data.get("metadata", {})
                    messages = session_data.get("messages", [])
                    
                    session_info = {
                        "session_id": session_data.get("session_id", session_file.stem),
                        "started_at": session_data.get("started_at"),
                        "message_count": len(messages),
                        "backend_type": metadata.get("backend_type"),
                        "model": metadata.get("model"),
                        "last_modified": datetime.fromtimestamp(session_file.stat().st_mtime).isoformat(),
                        "preview": self._get_session_preview(messages)
                    }
                    sessions.append(session_info)
                    
                except Exception as e:
                    self.logger.warning("Failed to read session file", 
                                      file=str(session_file), error=str(e))
                    continue
            
            return sessions
            
        except Exception as e:
            self.logger.error("Failed to get recent sessions", error=str(e))
            return []
    
    def _get_session_preview(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a preview of the conversation."""
        if not messages:
            return "Empty conversation"
        
        # Get the first user message as preview
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                content = msg["content"]
                # Truncate and clean up the preview
                preview = content.replace("\n", " ").strip()
                if len(preview) > 60:
                    preview = preview[:57] + "..."
                return preview
        
        return f"Conversation with {len(messages)} messages"
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a conversation session."""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return False
        
        try:
            session_file.unlink()
            self.logger.info("Deleted conversation session", session_id=session_id)
            return True
        except Exception as e:
            self.logger.error("Failed to delete session", session_id=session_id, error=str(e))
            return False
    
    async def export_session(self, session_id: str, export_path: Path, format: str = "json") -> bool:
        """Export a conversation session to a file."""
        session_file = self.history_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return False
        
        try:
            async with aiofiles.open(session_file, 'r') as f:
                content = await f.read()
                session_data = json.loads(content)
            
            if format.lower() == "json":
                # Export as JSON
                async with aiofiles.open(export_path, 'w') as f:
                    await f.write(json.dumps(session_data, indent=2))
            
            elif format.lower() == "txt":
                # Export as plain text
                lines = [f"Conversation Session: {session_data.get('session_id', 'Unknown')}"]
                lines.append(f"Started: {session_data.get('started_at', 'Unknown')}")
                lines.append(f"Messages: {len(session_data.get('messages', []))}")
                lines.append("=" * 50)
                lines.append("")
                
                for msg in session_data.get("messages", []):
                    role = msg.get("role", "unknown").title()
                    content = msg.get("content", "")
                    timestamp = msg.get("timestamp", "")
                    
                    lines.append(f"[{timestamp}] {role}:")
                    lines.append(content)
                    lines.append("")
                
                async with aiofiles.open(export_path, 'w') as f:
                    await f.write("\n".join(lines))
            
            self.logger.info("Exported conversation session", 
                           session_id=session_id, 
                           export_path=str(export_path))
            return True
            
        except Exception as e:
            self.logger.error("Failed to export session", 
                            session_id=session_id, 
                            error=str(e))
            return False
    
    async def cleanup_old_sessions(self, days_to_keep: int = 30) -> int:
        """Clean up old conversation sessions."""
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            session_files = list(self.history_dir.glob("conversation_*.json"))
            
            for session_file in session_files:
                if session_file.stat().st_mtime < cutoff_time:
                    try:
                        session_file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        self.logger.warning("Failed to delete old session file", 
                                          file=str(session_file), error=str(e))
            
            if deleted_count > 0:
                self.logger.info("Cleaned up old conversation sessions", 
                               deleted_count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            self.logger.error("Failed to cleanup old sessions", error=str(e))
            return 0