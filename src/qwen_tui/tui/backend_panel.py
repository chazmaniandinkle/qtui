from __future__ import annotations

from typing import Optional, List

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Static, Select, Label, Button

from ..backends.manager import BackendManager
from ..config import BackendType


class BackendPanel(Container):
    """Panel showing backend information and controls."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend_manager: Optional[BackendManager] = None
        self.update_timer = None

    def compose(self) -> ComposeResult:
        yield Static("🔧 Backend Panel", classes="panel-title")
        with Horizontal(id="backend-controls"):
            yield Label("Backend:")
            yield Select(options=[], id="backend-select")
            yield Label("Model:")
            yield Select(options=[], id="model-select")
        yield ScrollableContainer(
            Static("Initializing backends...", id="backend-status"),
            id="backend-content",
        )

    async def on_mount(self) -> None:
        """Initialize the backend panel."""
        self.backend_manager = self.app.backend_manager
        if self.backend_manager:
            await self._populate_backends()
            await self.update_backend_info()
            self.update_timer = self.set_interval(5.0, self.update_backend_info)

    async def _populate_backends(self) -> None:
        """Populate backend dropdown."""
        select = self.query_one("#backend-select", Select)
        options = [(bt.value, bt.value) for bt in self.backend_manager.backends.keys()]
        select.options = options
        preferred = self.backend_manager.get_status_summary().get("preferred_backend")
        if preferred:
            select.value = preferred
            await self._populate_models(BackendType(preferred))

    async def _populate_models(self, backend: BackendType) -> None:
        """Populate model dropdown for a backend."""
        model_select = self.query_one("#model-select", Select)
        models = await self.backend_manager.get_models_by_backend(backend)
        model_options: List[tuple[str, str]] = []
        for m in models:
            model_options.append((m["id"], m["id"]))
        model_select.options = model_options
        current_models = await self.backend_manager.get_current_models()
        current = current_models.get(backend.value)
        if current:
            model_select.value = current

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle backend/model dropdown changes."""
        if event.select.id == "backend-select":
            backend = BackendType(event.value)
            success = await self.backend_manager.switch_backend(backend)
            if success:
                await self._populate_models(backend)
                self.app.current_backend = backend.value
                self.app.add_system_message(f"Switched to backend: {backend.value}")
            else:
                self.app.add_error_message(f"Failed to switch to backend: {backend.value}")
        elif event.select.id == "model-select":
            backend_value = self.query_one("#backend-select", Select).value
            backend = BackendType(backend_value)
            model_id = event.value
            success = await self.backend_manager.switch_model(backend, model_id)
            if success:
                self.app.add_system_message(f"Switched {backend.value} to model {model_id}")
            else:
                self.app.add_error_message(
                    f"Failed to switch {backend.value} to model {model_id}")

    async def update_backend_info(self) -> None:
        """Update backend information display."""
        if not self.backend_manager:
            return
        try:
            backend_info = await self.backend_manager.get_backend_info()
            current_models = await self.backend_manager.get_current_models()
            status_summary = self.backend_manager.get_status_summary()
            content: List[str] = []
            total = status_summary.get("total_backends", 0)
            available = status_summary.get("available_backends", 0)
            preferred = status_summary.get("preferred_backend", "None")
            content.append(f"📊 Status: {available}/{total} backends available")
            content.append(f"🎯 Preferred: {preferred}")
            content.append("")
            if backend_info:
                for backend_type, info in backend_info.items():
                    name = info.get("name", backend_type.value)
                    status = info.get("status", "unknown")
                    if status == "ready":
                        indicator = "🟢"
                    elif status == "error":
                        indicator = "🔴"
                    else:
                        indicator = "🟡"
                    content.append(f"{indicator} {name}")
                    host = info.get("host", "N/A")
                    port = info.get("port", "N/A")
                    content.append(f"   📡 {host}:{port}")
                    current_model = current_models.get(backend_type.value, "None")
                    if current_model:
                        display_model = current_model
                        if len(display_model) > 30:
                            display_model = display_model[:27] + "..."
                        content.append(f"   🤖 Model: {display_model}")
                    else:
                        content.append("   🤖 Model: None loaded")
                    version = info.get("version", "Unknown")
                    if version != "Unknown":
                        content.append(f"   📋 Version: {version}")
                    error = info.get("error")
                    if error:
                        error_preview = error[:50] + "..." if len(error) > 50 else error
                        content.append(f"   ⚠️  Error: {error_preview}")
                    content.append("")
            else:
                content.append("No backend information available")
            backend_status = self.query_one("#backend-status", Static)
            backend_status.update("\n".join(content))
        except Exception as e:
            backend_status = self.query_one("#backend-status", Static)
            backend_status.update(f"❌ Error updating backend info:\n{str(e)}")

    def on_unmount(self) -> None:
        if self.update_timer:
            self.update_timer.stop()
