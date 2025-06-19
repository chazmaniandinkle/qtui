from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Optional

from textual.containers import ScrollableContainer

from ..backends.base import LLMRequest
from ..backends.manager import BackendManager
from ..config import Config
from ..history import ConversationHistory
from ..logging import get_main_logger
from .widgets import ChatMessage, ThinkingWidget, ActionWidget
from .backend_panel import BackendPanel
from .status_panel import StatusPanel


class ChatHandlersMixin:
    """Mixin providing chat command and history helpers."""

    backend_manager: BackendManager
    history_manager: ConversationHistory
    config: Config
    logger = get_main_logger()

    async def send_message(self, message: str) -> None:
        if not message.strip():
            return
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        user_msg = ChatMessage("user", message)
        await chat_scroll.mount(user_msg)
        user_msg.scroll_visible()

        user_message = {"role": "user", "content": message}
        self.conversation_history.append(user_message)
        self.message_count += 1

        try:
            backend = self.backend_manager.get_preferred_backend()
            backend_name = backend.name if backend else None
            model_name = getattr(backend, "_current_model", None) if backend else None
            await self.history_manager.save_message(user_message, backend_name, model_name)
        except Exception as e:
            sys_msg = ChatMessage("system", f"Failed to save user message: {e}")
            await chat_scroll.mount(sys_msg)
            sys_msg.scroll_visible()

        self.current_thinking_widget = ThinkingWidget("Analyzing your request...")
        await chat_scroll.mount(self.current_thinking_widget)
        self.current_thinking_widget.scroll_visible()
        self.current_thinking_widget.start_thinking()

        assistant_msg = ChatMessage("assistant", "")
        await chat_scroll.mount(assistant_msg)
        assistant_msg.scroll_visible()

        try:
            if self.thinking_manager:
                response_content = ""
                async for chunk in self.thinking_manager.think_and_respond(self.conversation_history.copy()):
                    response_content += chunk
                    assistant_msg.update_content(response_content)
                    assistant_msg.scroll_visible()
            else:
                request = LLMRequest(messages=self.conversation_history.copy(), stream=True)
                full_response = ""
                async for response in self.backend_manager.generate(request):
                    if response.is_partial and response.delta:
                        full_response += response.delta
                    elif response.content and not response.is_partial:
                        full_response = response.content
                response_content, thinking_content = self._filter_thinking_tags(full_response)
                if self.current_thinking_widget and thinking_content:
                    self.current_thinking_widget.set_full_thoughts(thinking_content)
                    self.current_thinking_widget.update_thinking_text("Found internal reasoning in response")
                assistant_msg.update_content(response_content)
                assistant_msg.scroll_visible()
                if self.current_thinking_widget:
                    self.current_thinking_widget.stop_thinking()
                    self.current_thinking_widget.update_thinking_text("Used direct backend with thinking filtering")
                    self.current_thinking_widget = None

            if response_content:
                filtered_content, _ = self._filter_thinking_tags(response_content)
                assistant_message = {"role": "assistant", "content": filtered_content}
                self.conversation_history.append(assistant_message)
                self.message_count += 1
                try:
                    await self.history_manager.save_message(assistant_message, backend_name, model_name)
                except Exception as e:
                    sys_msg = ChatMessage("system", f"Failed to save assistant message: {e}")
                    await chat_scroll.mount(sys_msg)
                    sys_msg.scroll_visible()
        except Exception as e:
            if self.current_thinking_widget:
                self.current_thinking_widget.stop_thinking()
                self.current_thinking_widget.update_thinking_text(f"Error: {str(e)}")
                self.current_thinking_widget = None
            err_msg = ChatMessage("error", f"Error: {str(e)}")
            await chat_scroll.mount(err_msg)
            err_msg.scroll_visible()

    async def handle_command(self, command: str) -> None:
        parts = command[1:].split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        if cmd == "help":
            self.action_show_help()
        elif cmd == "clear":
            self.action_new_conversation()
            self.add_system_message("Conversation cleared.")
        elif cmd == "quit":
            self.action_quit()
        elif cmd == "backends":
            backend_info = await self.backend_manager.get_backend_info()
            info_text = "Available Backends:\n"
            for backend_type, info in backend_info.items():
                status = info.get("status", "unknown")
                name = info.get("name", backend_type.value)
                info_text += f"- {name}: {status}\n"
            self.add_system_message(info_text)
        elif cmd == "models":
            self.action_show_model_selector()
        elif cmd == "switch" and args:
            backend_name = args[0].lower()
            self.add_system_message(f"Backend switching to {backend_name} (not implemented yet)")
        elif cmd == "history":
            asyncio.create_task(self._show_conversation_history())
        elif cmd == "load" and args:
            session_id = args[0]
            asyncio.create_task(self._load_conversation_session(session_id))
        elif cmd == "export" and args:
            if len(args) >= 2:
                session_id, format_type = args[0], args[1]
            else:
                session_id, format_type = self.current_session_id or "", (args[0] if args else "json")
            asyncio.create_task(self._export_conversation_session(session_id, format_type))
        elif cmd == "permissions":
            await self._handle_permission_command(args)
        else:
            self.add_error_message(f"Unknown command: /{cmd}")

    async def _show_conversation_history(self) -> None:
        try:
            sessions = await self.history_manager.get_recent_sessions(limit=10)
            chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
            if not sessions:
                no_history_message = ChatMessage("system", "No conversation history found.")
                await chat_scroll.mount(no_history_message)
                no_history_message.scroll_visible()
                return
            history_text = "Recent Conversations:\n\n"
            for session in sessions:
                started = session.get("started_at", "Unknown")[:16].replace("T", " ")
                preview = session.get("preview", "No content")
                message_count = session.get("message_count", 0)
                session_id = session.get("session_id", "unknown")
                history_text += f"• {started} - {message_count} messages\n"
                history_text += f"  ID: {session_id}\n"
                history_text += f"  Preview: {preview}\n\n"
            history_text += "Use '/load <session_id>' to load a conversation."
            history_message = ChatMessage("system", history_text)
            await chat_scroll.mount(history_message)
            history_message.scroll_visible()
        except Exception as e:
            error_msg = ChatMessage("error", f"Failed to load conversation history: {str(e)}")
            await chat_scroll.mount(error_msg)
            error_msg.scroll_visible()

    async def _load_conversation_session(self, session_id: str) -> None:
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        for child in list(chat_scroll.children):
            child.remove()
        try:
            messages = await self.history_manager.load_session(session_id)
            self.conversation_history = messages.copy()
            self.message_count = len(messages)
            for message in messages:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                msg_widget = ChatMessage(role, content)
                await chat_scroll.mount(msg_widget)
                msg_widget.scroll_visible()
            self.current_session_id = session_id
            sys_msg = ChatMessage("system", f"Loaded conversation session: {session_id}")
            await chat_scroll.mount(sys_msg)
            sys_msg.scroll_visible()
            self.logger.info("Loaded conversation session", session_id=session_id)
        except Exception as e:
            err_msg = ChatMessage("error", f"Failed to load session: {e}")
            await chat_scroll.mount(err_msg)
            err_msg.scroll_visible()

    async def _export_conversation_session(self, session_id: str, format_type: str) -> None:
        try:
            if not session_id:
                session_id = self.current_session_id
            if not session_id:
                chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
                no_session_msg = ChatMessage("error", "No session to export.")
                await chat_scroll.mount(no_session_msg)
                no_session_msg.scroll_visible()
                return
            export_dir = Path.home() / "Downloads"
            export_dir.mkdir(exist_ok=True)
            export_file = export_dir / f"qwen_conversation_{session_id}.{format_type}"
            success = await self.history_manager.save_session(session_id, export_file, format_type)
            chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
            if success:
                success_msg = ChatMessage("system", f"Exported conversation to: {export_file}")
                await chat_scroll.mount(success_msg)
                success_msg.scroll_visible()
            else:
                error_msg = ChatMessage("error", "Failed to export conversation.")
                await chat_scroll.mount(error_msg)
                error_msg.scroll_visible()
        except Exception as e:
            error_msg = ChatMessage("error", f"Export failed: {str(e)}")
            await chat_scroll.mount(error_msg)
            error_msg.scroll_visible()

    async def _handle_permission_command(self, args: list) -> None:
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        if not args:
            self.action_show_permissions()
            return
        subcommand = args[0].lower()
        if subcommand == "clear":
            if len(args) < 2:
                error_msg = ChatMessage("error", "Usage: /permissions clear <tool_name>")
                await chat_scroll.mount(error_msg)
                error_msg.scroll_visible()
                return
            tool_name = args[1]
            self.permission_manager.clear_preference(tool_name)
            success_msg = ChatMessage("system", f"Cleared preferences for tool: {tool_name}")
            await chat_scroll.mount(success_msg)
            success_msg.scroll_visible()
        elif subcommand == "yolo":
            if self.permission_manager.yolo_mode:
                self.permission_manager.yolo_mode = False
                mode_msg = ChatMessage("system", "🛡️ YOLO mode disabled. Security checks re-enabled.")
            else:
                self.permission_manager.yolo_mode = True
                mode_msg = ChatMessage("system", "⚠️ YOLO mode enabled. All security checks bypassed!")
            await chat_scroll.mount(mode_msg)
            mode_msg.scroll_visible()
        elif subcommand == "status":
            self.action_show_permissions()
        else:
            error_msg = ChatMessage(
                "error",
                f"Unknown permission command: {subcommand}\n" "Available: clear <tool>, yolo, status",
            )
            await chat_scroll.mount(error_msg)
            error_msg.scroll_visible()

    def _format_user_friendly_error(self, error: Exception) -> str:
        error_str = str(error)
        if "not found" in error_str.lower() and "model" in error_str.lower():
            return f"Model Error: {error_str}\n\nTip: Try using Ctrl+M to select an available model."
        elif "connection" in error_str.lower() or "connect" in error_str.lower():
            return f"Connection Error: {error_str}\n\nTip: Check if your backend service is running."
        elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
            return f"Timeout Error: {error_str}\n\nTip: The request took too long. Try a shorter message or check your connection."
        elif "unauthorized" in error_str.lower() or "api key" in error_str.lower():
            return f"Authentication Error: {error_str}\n\nTip: Check your API key configuration."
        else:
            return f"Error: {error_str}"

    def _format_unexpected_error(self, error: Exception) -> str:
        error_type = type(error).__name__
        error_str = str(error)
        if "ConnectionError" in error_type or "TimeoutError" in error_type:
            return "Network Error: Unable to connect to the backend service.\n\nTip: Check if the service is running and accessible."
        elif "MemoryError" in error_type:
            return "Memory Error: Not enough memory to process the request.\n\nTip: Try a shorter message or restart the application."
        else:
            return f"Unexpected Error ({error_type}): {error_str}\n\nTip: Try restarting the application. If the problem persists, check the logs."

    def _validate_message_input(self, message: str) -> Optional[str]:
        message = message.strip()
        if len(message) > 32000:
            return "Message too long. Please keep messages under 32,000 characters."
        lines = message.split("\n")
        max_line_length = max(len(line) for line in lines) if lines else 0
        if max_line_length > 2000:
            return "Message contains very long lines. Please break up long lines for better readability."
        if message.count("\n") > 200:
            return "Message contains too many line breaks. Please format the text more concisely."
        if not any(c.isalnum() for c in message):
            return "Message must contain some alphanumeric characters."
        return None

    def _filter_thinking_tags(self, content: str) -> tuple[str, str]:
        thinking_pattern = r"<think>(.*?)</think>"
        thinking_matches = re.findall(thinking_pattern, content, re.DOTALL | re.IGNORECASE)
        thinking_content = "\n".join(thinking_matches) if thinking_matches else ""
        visible_content = re.sub(thinking_pattern, "\n\n", content, flags=re.DOTALL | re.IGNORECASE)
        visible_content = re.sub(r"\n{3,}", "\n\n", visible_content)
        visible_content = re.sub(r"^\n+|\n+$", "", visible_content)
        return visible_content, thinking_content

    def clear_chat(self) -> None:
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        for child in list(chat_scroll.children):
            child.remove()

    def add_system_message(self, content: str) -> None:
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        if hasattr(chat_scroll, "add_system_message"):
            chat_scroll.add_system_message(content)
        else:
            sys_msg = ChatMessage("system", content)
            chat_scroll.mount(sys_msg)
            sys_msg.scroll_visible()

    def add_error_message(self, content: str) -> None:
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        if hasattr(chat_scroll, "add_error_message"):
            chat_scroll.add_error_message(content)
        else:
            err_msg = ChatMessage("error", content)
            chat_scroll.mount(err_msg)
            err_msg.scroll_visible()
