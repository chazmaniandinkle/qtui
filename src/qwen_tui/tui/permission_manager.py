"""
Permission manager integration for the TUI interface.

Bridges the permission system with the UI components for interactive permission requests.
"""
import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass

from ..agents.permissions import PermissionManager, RiskAssessment, PermissionAction
from ..logging import get_main_logger
from .permission_dialog import (
    PermissionDialog, 
    AlwaysAllowDialog, 
    get_permission_preferences
)


@dataclass
class PermissionResult:
    """Result of a permission request."""
    allowed: bool
    remember_decision: bool = False
    user_cancelled: bool = False


class TUIPermissionManager:
    """Permission manager that integrates with the TUI interface."""
    
    def __init__(self, app, working_directory: Optional[str] = None, yolo_mode: bool = False):
        self.app = app
        self.logger = get_main_logger()
        self.core_manager = PermissionManager(working_directory, yolo_mode)
        self.preferences = get_permission_preferences()
        
        # Track pending permission requests to avoid duplicates
        self.pending_requests = set()
    
    async def request_permission(self, tool_name: str, parameters: Dict[str, Any]) -> PermissionResult:
        """Request permission for a tool operation with UI interaction."""
        # Create unique key for this request to prevent duplicates
        request_key = f"{tool_name}:{hash(str(sorted(parameters.items())))}"
        
        if request_key in self.pending_requests:
            self.logger.debug("Duplicate permission request blocked", tool=tool_name)
            return PermissionResult(allowed=False, user_cancelled=True)
        
        self.pending_requests.add(request_key)
        
        try:
            # Get risk assessment from core permission manager
            assessment = self.core_manager.assess_tool_permission(tool_name, parameters)
            
            # Handle different permission actions
            if assessment.action == PermissionAction.ALLOW:
                result = PermissionResult(allowed=True)
                self.core_manager.log_permission_decision(
                    tool_name, parameters, assessment, "auto_allowed"
                )
                return result
            
            elif assessment.action == PermissionAction.BLOCK:
                result = PermissionResult(allowed=False)
                self.core_manager.log_permission_decision(
                    tool_name, parameters, assessment, "auto_blocked"
                )
                # Show blocking message to user
                await self._show_blocked_message(tool_name, assessment)
                return result
            
            else:  # PermissionAction.PROMPT
                # Check user preferences first
                if self.preferences.is_always_allowed(tool_name):
                    result = PermissionResult(allowed=True)
                    self.core_manager.log_permission_decision(
                        tool_name, parameters, assessment, "always_allowed"
                    )
                    return result
                
                if self.preferences.is_always_denied(tool_name):
                    result = PermissionResult(allowed=False)
                    self.core_manager.log_permission_decision(
                        tool_name, parameters, assessment, "always_denied"
                    )
                    return result
                
                # Show permission dialog
                return await self._show_permission_dialog(tool_name, parameters, assessment)
        
        finally:
            self.pending_requests.discard(request_key)
    
    async def _show_permission_dialog(self, tool_name: str, parameters: Dict[str, Any], 
                                    assessment: RiskAssessment) -> PermissionResult:
        """Show the permission dialog and handle user response."""
        try:
            # Create and show permission dialog
            dialog = PermissionDialog(tool_name, parameters, assessment)
            decision = await self.app.push_screen_wait(dialog)
            
            if decision == "allow":
                # Check if user wants to remember this decision
                remember_result = await self._ask_remember_decision(tool_name)
                
                if remember_result == "always_allow":
                    self.preferences.set_always_allow(tool_name)
                    remember_decision = True
                else:
                    remember_decision = False
                
                result = PermissionResult(allowed=True, remember_decision=remember_decision)
                self.core_manager.log_permission_decision(
                    tool_name, parameters, assessment, "user_allowed"
                )
                return result
            
            elif decision == "deny":
                # Check if user wants to remember this decision
                remember_result = await self._ask_remember_decision(tool_name)
                
                if remember_result == "always_allow":  # This would be "always_deny" for deny
                    # Note: We don't implement "always deny" to avoid accidentally blocking useful operations
                    remember_decision = False
                else:
                    remember_decision = False
                
                result = PermissionResult(allowed=False, remember_decision=remember_decision)
                self.core_manager.log_permission_decision(
                    tool_name, parameters, assessment, "user_denied"
                )
                return result
            
            else:
                # User cancelled/escaped
                result = PermissionResult(allowed=False, user_cancelled=True)
                self.core_manager.log_permission_decision(
                    tool_name, parameters, assessment, "user_cancelled"
                )
                return result
        
        except Exception as e:
            self.logger.error("Error showing permission dialog", error=str(e))
            # Fail safe - deny permission on error
            result = PermissionResult(allowed=False, user_cancelled=True)
            self.core_manager.log_permission_decision(
                tool_name, parameters, assessment, "dialog_error"
            )
            return result
    
    async def _ask_remember_decision(self, tool_name: str) -> str:
        """Ask user if they want to remember their decision."""
        try:
            dialog = AlwaysAllowDialog(tool_name)
            result = await self.app.push_screen_wait(dialog)
            return result or "ask_each_time"
        except Exception as e:
            self.logger.error("Error showing remember decision dialog", error=str(e))
            return "ask_each_time"
    
    async def _show_blocked_message(self, tool_name: str, assessment: RiskAssessment):
        """Show a message when an operation is automatically blocked."""
        try:
            # Add a system message to the chat explaining why the operation was blocked
            if hasattr(self.app, 'add_error_message'):
                message = f"🚫 Operation blocked: {tool_name}\n\n"
                if assessment.reasons:
                    message += "Reasons:\n"
                    for reason in assessment.reasons:
                        message += f"  • {reason}\n"
                
                if assessment.warnings:
                    message += "\nWarnings:\n" 
                    for warning in assessment.warnings:
                        message += f"  • {warning}\n"
                
                self.app.add_error_message(message)
        except Exception as e:
            self.logger.error("Error showing blocked message", error=str(e))
    
    def enable_yolo_mode(self) -> None:
        """Enable YOLO mode (bypass all permissions)."""
        self.core_manager.enable_yolo_mode()
    
    def disable_yolo_mode(self) -> None:
        """Disable YOLO mode (re-enable permissions)."""
        self.core_manager.disable_yolo_mode()
    
    def get_permission_summary(self) -> str:
        """Get a summary of recent permission decisions."""
        return self.core_manager.get_permission_summary()
    
    def clear_preferences(self, tool_name: Optional[str] = None) -> None:
        """Clear permission preferences for a tool or all tools."""
        if tool_name:
            self.preferences.clear_preference(tool_name)
        else:
            self.preferences.always_allow_tools.clear()
            self.preferences.always_deny_tools.clear()
        self.preferences.save_preferences()


class PermissionIntegrator:
    """Integrates permission checking into the tool execution pipeline."""
    
    def __init__(self, tui_permission_manager: TUIPermissionManager):
        self.permission_manager = tui_permission_manager
        self.logger = get_main_logger()
    
    async def check_tool_permission(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Check if a tool operation is permitted."""
        try:
            result = await self.permission_manager.request_permission(tool_name, parameters)
            return result.allowed
        except Exception as e:
            self.logger.error("Permission check failed", tool=tool_name, error=str(e))
            # Fail safe - deny permission on error
            return False
    
    async def wrap_tool_execution(self, tool_name: str, parameters: Dict[str, Any], 
                                execute_func: Callable[[], Awaitable[Any]]) -> Any:
        """Wrap tool execution with permission checking."""
        # Check permission first
        if not await self.check_tool_permission(tool_name, parameters):
            raise PermissionError(f"Permission denied for {tool_name}")
        
        # Execute the tool
        return await execute_func()


# Global TUI permission manager instance
_global_tui_permission_manager: Optional[TUIPermissionManager] = None


def get_tui_permission_manager(app=None, working_directory: Optional[str] = None, 
                              yolo_mode: bool = False) -> TUIPermissionManager:
    """Get or create the global TUI permission manager."""
    global _global_tui_permission_manager
    if _global_tui_permission_manager is None and app is not None:
        _global_tui_permission_manager = TUIPermissionManager(app, working_directory, yolo_mode)
    return _global_tui_permission_manager


def set_tui_permission_manager(manager: TUIPermissionManager) -> None:
    """Set the global TUI permission manager."""
    global _global_tui_permission_manager
    _global_tui_permission_manager = manager