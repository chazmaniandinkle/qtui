"""
Permission dialog components for the TUI interface.

Provides modal dialogs for requesting user permission for potentially risky operations.
"""
from typing import Optional, Dict, Any, Tuple
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static, Button, Label
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.events import Click

from ..agents.permissions import RiskAssessment, RiskLevel


class PermissionDialog(ModalScreen):
    """Modal dialog for requesting permission to execute risky operations."""
    
    BINDINGS = [
        Binding("escape", "deny", "Deny"),
        Binding("enter", "allow", "Allow"),
        Binding("d", "show_details", "Details"),
    ]
    
    def __init__(self, tool_name: str, parameters: Dict[str, Any], 
                 assessment: RiskAssessment, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.parameters = parameters
        self.assessment = assessment
        self.show_details = False
        
    def compose(self) -> ComposeResult:
        """Compose the permission dialog UI."""
        with Container(id="permission-dialog"):
            yield Label("⚠️ Permission Required", id="dialog-title")
            
            # Risk level indicator
            yield RiskIndicator(self.assessment.risk_level)
            
            # Operation summary
            yield OperationSummary(self.tool_name, self.parameters)
            
            # Warnings (always visible)
            if self.assessment.warnings:
                yield WarningList(self.assessment.warnings)
            
            # Details section (expandable)
            yield DetailsSection(
                self.assessment.reasons, 
                self.assessment.suggestions,
                id="details-section",
                classes="hidden"
            )
            
            # Action buttons
            with Horizontal(id="dialog-buttons"):
                yield Button("Allow", id="allow-btn", variant="primary")
                yield Button("Deny", id="deny-btn", variant="error")
                yield Button("Details", id="details-btn")
    
    def action_allow(self) -> None:
        """Allow the operation."""
        self.dismiss("allow")
    
    def action_deny(self) -> None:
        """Deny the operation."""
        self.dismiss("deny")
    
    def action_show_details(self) -> None:
        """Toggle details section visibility."""
        details_section = self.query_one("#details-section")
        if details_section.has_class("hidden"):
            details_section.remove_class("hidden")
            self.show_details = True
            details_btn = self.query_one("#details-btn", Button)
            details_btn.label = "Hide Details"
        else:
            details_section.add_class("hidden")
            self.show_details = False
            details_btn = self.query_one("#details-btn", Button)
            details_btn.label = "Details"
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "allow-btn":
            self.action_allow()
        elif event.button.id == "deny-btn":
            self.action_deny()
        elif event.button.id == "details-btn":
            self.action_show_details()


class RiskIndicator(Static):
    """Widget that displays the risk level with appropriate styling."""
    
    def __init__(self, risk_level: RiskLevel, **kwargs):
        super().__init__(**kwargs)
        self.risk_level = risk_level
        self.add_class("risk-indicator")
        self.add_class(f"risk-{risk_level.value}")
        self.update_display()
    
    def update_display(self):
        """Update the risk indicator display."""
        risk_icons = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟡", 
            RiskLevel.MEDIUM: "🟠",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "⛔"
        }
        
        risk_labels = {
            RiskLevel.SAFE: "Safe Operation",
            RiskLevel.LOW: "Low Risk",
            RiskLevel.MEDIUM: "Medium Risk", 
            RiskLevel.HIGH: "High Risk",
            RiskLevel.CRITICAL: "Critical Risk"
        }
        
        icon = risk_icons.get(self.risk_level, "⚪")
        label = risk_labels.get(self.risk_level, "Unknown Risk")
        
        self.update(f"{icon} {label}")


class OperationSummary(Static):
    """Widget that displays a summary of the operation to be performed."""
    
    def __init__(self, tool_name: str, parameters: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.parameters = parameters
        self.add_class("operation-summary")
        self.update_display()
    
    def update_display(self):
        """Update the operation summary display."""
        content = f"**Tool:** {self.tool_name}\n\n"
        
        # Format parameters for display
        if self.parameters:
            content += "**Parameters:**\n"
            for key, value in self.parameters.items():
                # Truncate very long values
                str_value = str(value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                
                # Handle multi-line values
                if '\n' in str_value:
                    lines = str_value.split('\n')
                    if len(lines) > 3:
                        str_value = '\n'.join(lines[:3]) + f"\n... ({len(lines)-3} more lines)"
                
                content += f"  • {key}: {str_value}\n"
        else:
            content += "*No parameters*"
        
        self.update(content)


class WarningList(Static):
    """Widget that displays warnings about the operation."""
    
    def __init__(self, warnings: list, **kwargs):
        super().__init__(**kwargs)
        self.warnings = warnings
        self.add_class("warning-list")
        self.update_display()
    
    def update_display(self):
        """Update the warnings display."""
        if not self.warnings:
            return
        
        content = "**⚠️ Warnings:**\n"
        for warning in self.warnings:
            content += f"  • {warning}\n"
        
        self.update(content)


class DetailsSection(Container):
    """Expandable section containing detailed permission information."""
    
    def __init__(self, reasons: list, suggestions: list, **kwargs):
        super().__init__(**kwargs)
        self.reasons = reasons
        self.suggestions = suggestions
    
    def compose(self) -> ComposeResult:
        """Compose the details section."""
        with ScrollableContainer():
            if self.reasons:
                yield Static("**🔍 Analysis:**", classes="section-header")
                for reason in self.reasons:
                    yield Static(f"  • {reason}", classes="detail-item")
                yield Static("")  # Spacing
            
            if self.suggestions:
                yield Static("**💡 Suggestions:**", classes="section-header")
                for suggestion in self.suggestions:
                    yield Static(f"  • {suggestion}", classes="detail-item")


class AlwaysAllowDialog(ModalScreen):
    """Dialog for asking if user wants to always allow this type of operation."""
    
    BINDINGS = [
        Binding("escape", "no", "No"),
        Binding("enter", "yes", "Yes"),
    ]
    
    def __init__(self, tool_name: str, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
    
    def compose(self) -> ComposeResult:
        """Compose the always allow dialog."""
        with Container(id="always-allow-dialog"):
            yield Label("Remember This Decision?", id="always-title")
            yield Static(
                f"Do you want to always allow {self.tool_name} operations?\n\n"
                "You can change this later in the settings.",
                id="always-message"
            )
            
            with Horizontal(id="always-buttons"):
                yield Button("Yes, Always Allow", id="yes-btn", variant="primary")
                yield Button("No, Ask Each Time", id="no-btn")
    
    def action_yes(self) -> None:
        """Always allow this tool."""
        self.dismiss("always_allow")
    
    def action_no(self) -> None:
        """Don't always allow.""" 
        self.dismiss("ask_each_time")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "yes-btn":
            self.action_yes()
        elif event.button.id == "no-btn":
            self.action_no()


class PermissionPreferences:
    """Manages user preferences for permission decisions."""
    
    def __init__(self):
        self.always_allow_tools = set()
        self.always_deny_tools = set()
        self.preferences_file = None  # Will be set by config system
    
    def is_always_allowed(self, tool_name: str) -> bool:
        """Check if a tool is always allowed."""
        return tool_name in self.always_allow_tools
    
    def is_always_denied(self, tool_name: str) -> bool:
        """Check if a tool is always denied."""
        return tool_name in self.always_deny_tools
    
    def set_always_allow(self, tool_name: str) -> None:
        """Set a tool to always be allowed."""
        self.always_allow_tools.add(tool_name)
        self.always_deny_tools.discard(tool_name)
        self.save_preferences()
    
    def set_always_deny(self, tool_name: str) -> None:
        """Set a tool to always be denied."""
        self.always_deny_tools.add(tool_name)
        self.always_allow_tools.discard(tool_name)
        self.save_preferences()
    
    def clear_preference(self, tool_name: str) -> None:
        """Clear any preference for a tool."""
        self.always_allow_tools.discard(tool_name)
        self.always_deny_tools.discard(tool_name)
        self.save_preferences()
    
    def save_preferences(self) -> None:
        """Save preferences to file (placeholder for now)."""
        # TODO: Implement file-based persistence
        pass
    
    def load_preferences(self) -> None:
        """Load preferences from file (placeholder for now)."""
        # TODO: Implement file-based persistence
        pass


# Global preferences instance
_permission_preferences = PermissionPreferences()


def get_permission_preferences() -> PermissionPreferences:
    """Get the global permission preferences instance."""
    return _permission_preferences