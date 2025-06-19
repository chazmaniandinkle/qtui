"""
Permission dialog UI components for visual permission management.

Provides interactive dialogs for tool permission requests with risk assessment
and user preference collection.
"""
from typing import Optional, Callable, Any, Dict

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label
from textual.events import Click

from ..agents.permissions import RiskAssessment, RiskLevel, PermissionAction


class RiskIndicator(Static):
    """Visual risk level indicator with appropriate styling."""
    
    def __init__(self, risk_level: RiskLevel, **kwargs):
        super().__init__(**kwargs)
        self.risk_level = risk_level
        self._update_content()
    
    def _update_content(self):
        """Update content based on risk level."""
        indicators = {
            RiskLevel.SAFE: "🟢 SAFE",
            RiskLevel.LOW: "🟡 LOW RISK", 
            RiskLevel.MEDIUM: "🟠 MEDIUM RISK",
            RiskLevel.HIGH: "🔴 HIGH RISK",
            RiskLevel.CRITICAL: "⛔ CRITICAL"
        }
        
        self.update(indicators.get(self.risk_level, "❓ UNKNOWN"))
        
        # Add CSS classes for styling
        self.remove_class("safe", "low", "medium", "high", "critical")
        self.add_class(f"risk-{self.risk_level.value}")


class OperationSummary(Static):
    """Summary of the operation being requested."""
    
    def __init__(self, tool_name: str, parameters: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.parameters = parameters
        self._update_content()
    
    def _update_content(self):
        """Build operation summary content."""
        content = [f"🔧 Tool: {self.tool_name}"]
        
        # Show key parameters
        if self.parameters:
            content.append("📋 Parameters:")
            for key, value in list(self.parameters.items())[:3]:  # Limit to 3 params
                # Truncate long values
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                content.append(f"   • {key}: {value}")
            
            if len(self.parameters) > 3:
                content.append(f"   • ... and {len(self.parameters) - 3} more")
        
        self.update("\n".join(content))


class WarningList(Static):
    """Display warnings and reasons for the permission request."""
    
    def __init__(self, assessment: RiskAssessment, **kwargs):
        super().__init__(**kwargs)
        self.assessment = assessment
        self._update_content()
    
    def _update_content(self):
        """Build warning content."""
        content = []
        
        if self.assessment.warnings:
            content.append("⚠️  Warnings:")
            for warning in self.assessment.warnings:
                content.append(f"   • {warning}")
            content.append("")
        
        if self.assessment.reasons:
            content.append("📋 Analysis:")
            for reason in self.assessment.reasons:
                content.append(f"   • {reason}")
        
        self.update("\n".join(content))


class DetailsSection(Container):
    """Expandable details section with suggestions and analysis."""
    
    def __init__(self, assessment: RiskAssessment, **kwargs):
        super().__init__(**kwargs)
        self.assessment = assessment
        self.is_expanded = False
        
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Button("📋 Show Details", id="toggle-details", variant="outline")
            yield Static("", id="details-content", classes="details-content hidden")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle details toggle."""
        if event.button.id == "toggle-details":
            self.toggle_details()
    
    def toggle_details(self):
        """Toggle details visibility."""
        self.is_expanded = not self.is_expanded
        details_content = self.query_one("#details-content", Static)
        toggle_button = self.query_one("#toggle-details", Button)
        
        if self.is_expanded:
            # Show details
            content = []
            
            if self.assessment.suggestions:
                content.append("💡 Suggestions:")
                for suggestion in self.assessment.suggestions:
                    content.append(f"   • {suggestion}")
                content.append("")
            
            content.append("🔍 Technical Details:")
            content.append(f"   • Risk Level: {self.assessment.risk_level.value.upper()}")
            content.append(f"   • Action: {self.assessment.action.value.upper()}")
            
            if hasattr(self.assessment, 'tool_name'):
                content.append(f"   • Tool: {self.assessment.tool_name}")
            
            details_content.update("\n".join(content))
            details_content.remove_class("hidden")
            toggle_button.label = "📋 Hide Details"
        else:
            # Hide details
            details_content.add_class("hidden")
            toggle_button.label = "📋 Show Details"


class PermissionDialog(ModalScreen):
    """Main permission request dialog."""
    
    BINDINGS = [
        Binding("enter", "allow", "Allow"),
        Binding("escape", "deny", "Deny"),
        Binding("d", "toggle_details", "Details"),
    ]
    
    def __init__(self, 
                 tool_name: str,
                 parameters: Dict[str, Any],
                 assessment: RiskAssessment,
                 callback: Callable[[bool, bool], None],
                 **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.parameters = parameters
        self.assessment = assessment
        self.callback = callback
        
    def compose(self) -> ComposeResult:
        with Container(id="permission-dialog"):
            # Header with risk indicator
            with Horizontal(id="dialog-header"):
                yield RiskIndicator(self.assessment.risk_level)
                yield Label("Permission Required", id="dialog-title")
            
            # Main content
            with ScrollableContainer(id="dialog-content"):
                yield OperationSummary(self.tool_name, self.parameters)
                yield Static("", id="spacer-1")
                yield WarningList(self.assessment)
                yield Static("", id="spacer-2")
                yield DetailsSection(self.assessment)
            
            # Footer with action buttons
            with Horizontal(id="dialog-footer"):
                yield Button("Allow Once", id="allow-once", variant="primary")
                yield Button("Always Allow", id="always-allow", variant="success")
                yield Button("Deny", id="deny", variant="error")
                yield Button("Always Deny", id="always-deny", variant="warning")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "allow-once":
            self.dismiss_with_result(True, False)
        elif button_id == "always-allow":
            self.dismiss_with_result(True, True)
        elif button_id == "deny":
            self.dismiss_with_result(False, False)
        elif button_id == "always-deny":
            self.dismiss_with_result(False, True)
    
    def action_allow(self) -> None:
        """Allow the operation."""
        self.dismiss_with_result(True, False)
    
    def action_deny(self) -> None:
        """Deny the operation."""
        self.dismiss_with_result(False, False)
    
    def action_toggle_details(self) -> None:
        """Toggle details section."""
        details_section = self.query_one(DetailsSection)
        details_section.toggle_details()
    
    def dismiss_with_result(self, allowed: bool, always: bool):
        """Dismiss dialog with result."""
        if always:
            # Show always allow/deny confirmation
            def on_confirm(confirmed: bool):
                if confirmed:
                    self.callback(allowed, always)
                    self.dismiss()
                # If not confirmed, stay on current dialog
            
            always_dialog = AlwaysAllowDialog(
                tool_name=self.tool_name,
                allowed=allowed,
                callback=on_confirm
            )
            self.app.push_screen(always_dialog)
        else:
            self.callback(allowed, always)
            self.dismiss()


class AlwaysAllowDialog(ModalScreen):
    """Confirmation dialog for always allow/deny decisions."""
    
    BINDINGS = [
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, 
                 tool_name: str,
                 allowed: bool,
                 callback: Callable[[bool], None],
                 **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.allowed = allowed
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        action = "ALLOW" if self.allowed else "DENY"
        icon = "✅" if self.allowed else "❌"
        
        with Container(id="always-dialog"):
            yield Label(f"{icon} Always {action}?", id="always-title")
            yield Static(
                f"This will always {action.lower()} the '{self.tool_name}' tool "
                f"without asking for permission.\n\n"
                f"You can change this later in permission settings.",
                id="always-message"
            )
            
            with Horizontal(id="always-buttons"):
                yield Button("Confirm", id="confirm", variant="primary")
                yield Button("Cancel", id="cancel", variant="outline")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "confirm":
            self.action_confirm()
        elif event.button.id == "cancel":
            self.action_cancel()
    
    def action_confirm(self) -> None:
        """Confirm the always decision."""
        self.callback(True)
        self.dismiss()
    
    def action_cancel(self) -> None:
        """Cancel the always decision."""
        self.callback(False)
        self.dismiss()


class PermissionPreferences:
    """Manages user permission preferences."""
    
    def __init__(self):
        self.always_allow: set[str] = set()
        self.always_deny: set[str] = set()
    
    def set_preference(self, tool_name: str, allow: bool):
        """Set tool preference."""
        # Clear any existing preference
        self.always_allow.discard(tool_name)
        self.always_deny.discard(tool_name)
        
        # Set new preference
        if allow:
            self.always_allow.add(tool_name)
        else:
            self.always_deny.add(tool_name)
    
    def get_preference(self, tool_name: str) -> Optional[bool]:
        """Get tool preference."""
        if tool_name in self.always_allow:
            return True
        elif tool_name in self.always_deny:
            return False
        return None
    
    def clear_preference(self, tool_name: str):
        """Clear tool preference."""
        self.always_allow.discard(tool_name)
        self.always_deny.discard(tool_name)
    
    def clear_all(self):
        """Clear all preferences."""
        self.always_allow.clear()
        self.always_deny.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get preference summary."""
        return {
            "always_allow": list(self.always_allow),
            "always_deny": list(self.always_deny),
            "total_preferences": len(self.always_allow) + len(self.always_deny)
        }