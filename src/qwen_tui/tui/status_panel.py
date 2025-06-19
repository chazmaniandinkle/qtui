from __future__ import annotations

import time
from typing import List

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Static


class StatusPanel(Container):
    """Panel showing application status and metrics."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.update_timer = None
        self.start_time = time.time()

    def compose(self) -> ComposeResult:
        yield Static("📊 Status Panel", classes="panel-title")
        yield ScrollableContainer(
            Static("Initializing...", id="status-display"), id="status-content"
        )

    async def on_mount(self) -> None:
        """Initialize the status panel."""
        await self.update_status_info()
        self.update_timer = self.set_interval(5.0, self.update_status_info)

    async def update_status_info(self) -> None:
        """Update status information display."""
        try:
            app = self.app
            content: List[str] = []

            uptime_seconds = int(time.time() - self.start_time)
            uptime_str = self._format_uptime(uptime_seconds)
            content.append(f"⏱️  Uptime: {uptime_str}")

            if hasattr(app, "current_session_id") and app.current_session_id:
                session_preview = (
                    app.current_session_id[:8] + "..."
                    if len(app.current_session_id) > 8
                    else app.current_session_id
                )
                content.append(f"💬 Session: {session_preview}")
            else:
                content.append("💬 Session: None")

            message_count = getattr(app, "message_count", 0)
            content.append(f"📝 Messages: {message_count}")

            if hasattr(app, "backend_manager") and app.backend_manager:
                status_summary = app.backend_manager.get_status_summary()
                total = status_summary.get("total_backends", 0)
                available = status_summary.get("available_backends", 0)
                content.append(f"🔧 Backends: {available}/{total} available")
                current_backend = getattr(app, "current_backend", None)
                if current_backend:
                    content.append(f"🎯 Active: {current_backend}")
                else:
                    content.append("🎯 Active: None")
            else:
                content.append("🔧 Backends: Not initialized")

            content.append("")

            if hasattr(app, "thinking_manager") and app.thinking_manager:
                thinking_state = app.thinking_manager.get_thinking_state()
                if thinking_state.is_thinking:
                    content.append("🧠 Thinking: Active")
                    if thinking_state.current_thought:
                        thought_preview = (
                            thinking_state.current_thought[:40] + "..."
                            if len(thinking_state.current_thought) > 40
                            else thinking_state.current_thought
                        )
                        content.append(f"   💭 {thought_preview}")
                    if thinking_state.active_tools:
                        tools_str = ", ".join(thinking_state.active_tools[:3])
                        if len(thinking_state.active_tools) > 3:
                            tools_str += "..."
                        content.append(f"   🔧 Tools: {tools_str}")
                else:
                    content.append("🧠 Thinking: Idle")

                completed_count = len(thinking_state.completed_actions)
                if completed_count > 0:
                    content.append(f"   ✅ Actions: {completed_count} completed")
            else:
                content.append("🧠 Thinking: Not available")

            content.append("")

            content.append("💻 System:")
            try:
                import psutil

                memory = psutil.virtual_memory()
                process = psutil.Process()
                memory_percent = memory.percent
                memory_available = memory.available // (1024**3)
                proc_mem = process.memory_info().rss // (1024 ** 2)
                content.append(
                    f"   🧠 Memory: {memory_percent:.1f}% used, {memory_available}GB free"
                )
                content.append(f"   🐍 Process: {proc_mem}MB")
            except ImportError:
                content.append("   🧠 Memory: N/A (psutil not available)")

            if hasattr(app, "backend_manager") and app.backend_manager:
                try:
                    backend_info = await app.backend_manager.get_backend_info()
                    test_results = await app.backend_manager.test_all_backends()
                    if backend_info and test_results:
                        content.append("   ⚡ Latency:")
                        for bt, info in backend_info.items():
                            name = info.get("name", getattr(bt, "value", str(bt)))
                            result = test_results.get(bt, {})
                            latency = result.get("response_time")
                            if latency is not None:
                                latency_ms = int(latency * 1000)
                                content.append(f"      {name}: {latency_ms} ms")
                except Exception:
                    pass

            try:
                size = app.size
                content.append(f"   📺 Terminal: {size.width}x{size.height}")
                if hasattr(app, "is_compact_layout"):
                    layout_mode = "Compact" if app.is_compact_layout else "Normal"
                    content.append(f"   🖼️  Layout: {layout_mode}")
            except Exception:
                content.append("   📺 Terminal: Size unknown")

            status_display = self.query_one("#status-display", Static)
            status_display.update("\n".join(content))
        except Exception as e:  # pragma: no cover - display failures are non-fatal
            error_content = f"❌ Error updating status info:\n{str(e)}"
            try:
                status_display = self.query_one("#status-display", Static)
                status_display.update(error_content)
            except Exception:
                pass

    def _format_uptime(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def on_unmount(self) -> None:
        if self.update_timer:
            self.update_timer.stop()
