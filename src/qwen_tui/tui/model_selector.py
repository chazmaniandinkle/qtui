from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from ..backends.manager import BackendManager


class ModelSelectorScreen(ModalScreen):
    """Modal screen for selecting models across backends."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select_model", "Select"),
    ]

    def __init__(self, backend_manager: BackendManager, **kwargs):
        super().__init__(**kwargs)
        self.backend_manager = backend_manager
        self.models: dict[int, tuple[str, str]] = {}
        self.selected_row = 0

    def compose(self) -> ComposeResult:
        with Container(id="model-selector"):
            yield Label("Select a Model", id="selector-title")
            yield DataTable(id="models-table", show_header=True, show_cursor=True)
            with Horizontal(id="selector-buttons"):
                yield Button("Select", id="select-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    async def on_mount(self) -> None:
        self.adjust_for_screen_size()
        await self.load_models()

    def adjust_for_screen_size(self) -> None:
        try:
            app_size = self.app.size
            if app_size.width < 70:
                pass
        except Exception:
            pass

    async def load_models(self) -> None:
        try:
            table = self.query_one("#models-table", DataTable)
            app_size = self.app.size
            if app_size.width < 70:
                table.add_columns("Backend", "Model", "Status")
            else:
                table.add_columns("Backend", "Model", "Type", "Status")

            all_models = await self.backend_manager.get_all_models()
            current_models = await self.backend_manager.get_current_models()

            row_data = []
            for backend_name, models in all_models.items():
                current_model = current_models.get(backend_name)
                for model in models:
                    model_id = model["id"]
                    status = "● Current" if model_id == current_model else "Available"
                    display_model_id = model_id
                    if app_size.width < 70 and len(model_id) > 30:
                        display_model_id = model_id[:27] + "..."
                    if app_size.width < 70:
                        table.add_row(
                            backend_name.title()[:8],
                            display_model_id,
                            status[:12],
                        )
                    else:
                        table.add_row(
                            backend_name.title(),
                            display_model_id,
                            model.get("object", "model"),
                            status,
                        )
                    row_data.append((backend_name, model_id))
            self.models = dict(enumerate(row_data))
        except Exception as e:
            error_msg = f"Failed to load models: {str(e)}"
            table = self.query_one("#models-table", DataTable)
            table.add_row("Error", error_msg, "", "")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_model(self) -> None:
        table = self.query_one("#models-table", DataTable)
        if table.cursor_row is not None and table.cursor_row in self.models:
            backend_type, model_id = self.models[table.cursor_row]
            self.dismiss((backend_type, model_id))
        else:
            self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-btn":
            self.action_select_model()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_row = event.row_key
        if event.row_key in self.models:
            backend_type, model_id = self.models[event.row_key]
            self.dismiss((backend_type, model_id))

