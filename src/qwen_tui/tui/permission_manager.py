"""
TUI Permission Manager - Bridge between UI and core permission system.

Provides async permission handling with user interaction for tool execution.
"""
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, Awaitable

from ..agents.permissions import PermissionManager, RiskAssessment, RiskLevel, PermissionAction
from ..logging import get_main_logger
from .permission_dialog import PermissionDialog, PermissionPreferences


@dataclass
class PermissionResult:
    """Result of a permission request."""
    allowed: bool
    always: bool
    assessment: RiskAssessment


class TUIPermissionManager:
    """TUI-aware permission manager with interactive dialogs."""
    
    def __init__(self, app, working_directory: Optional[str] = None, yolo_mode: bool = False):
        self.app = app
        self.core_manager = PermissionManager(working_directory, yolo_mode)
        self.preferences = PermissionPreferences()
        self.logger = get_main_logger()
        
        # Track pending permission requests to avoid duplicates
        self._pending_requests: Dict[str, asyncio.Future] = {}
    
    @property
    def yolo_mode(self) -> bool:
        """Check if YOLO mode is enabled."""
        return self.core_manager.yolo_mode
    
    @yolo_mode.setter
    def yolo_mode(self, value: bool):
        """Set YOLO mode."""
        self.core_manager.yolo_mode = value
        if value:
            self.logger.warning("YOLO mode enabled - all permissions bypassed")
        else:
            self.logger.info("YOLO mode disabled - permissions restored")
    
    async def request_permission(self, tool_name: str, parameters: Dict[str, Any]) -> PermissionResult:
        """Request permission for a tool operation with UI interaction."""
        # Create unique request key to prevent duplicate dialogs
        request_key = f"{tool_name}:{hash(frozenset(parameters.items()) if parameters else frozenset())}"
        
        # If there's already a pending request for this exact operation, wait for it
        if request_key in self._pending_requests:
            self.logger.debug(f"Waiting for existing permission request: {request_key}")
            return await self._pending_requests[request_key]
        
        # Create new permission request
        future = asyncio.Future()
        self._pending_requests[request_key] = future
        
        try:
            result = await self._handle_permission_request(tool_name, parameters)
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            # Clean up pending request
            self._pending_requests.pop(request_key, None)
    
    async def _handle_permission_request(self, tool_name: str, parameters: Dict[str, Any]) -> PermissionResult:
        """Handle individual permission request."""
        # Get core risk assessment
        assessment = self.core_manager.assess_tool_permission(tool_name, parameters)
        
        self.logger.debug(f"Permission request for {tool_name}: {assessment.risk_level.value} risk")
        
        # Check user preferences first
        preference = self.preferences.get_preference(tool_name)
        if preference is not None:
            self.logger.debug(f"Using saved preference for {tool_name}: {preference}")
            return PermissionResult(
                allowed=preference,
                always=True,  # This was a saved preference
                assessment=assessment
            )
        
        # Handle based on risk level and action
        if assessment.action == PermissionAction.ALLOW:
            # Auto-allow safe operations
            return PermissionResult(allowed=True, always=False, assessment=assessment)
        
        elif assessment.action == PermissionAction.BLOCK:
            # Auto-block critical operations
            self.logger.warning(f"Blocked {tool_name} operation: {assessment.risk_level.value} risk")
            # Still show dialog to inform user why it was blocked
            await self._show_blocked_dialog(tool_name, parameters, assessment)
            return PermissionResult(allowed=False, always=False, assessment=assessment)
        
        elif assessment.action == PermissionAction.PROMPT:
            # Show interactive permission dialog
            return await self._show_permission_dialog(tool_name, parameters, assessment)
        
        else:
            # Unknown action, default to deny
            self.logger.error(f"Unknown permission action: {assessment.action}")
            return PermissionResult(allowed=False, always=False, assessment=assessment)
    
    async def _show_permission_dialog(self, tool_name: str, parameters: Dict[str, Any], assessment: RiskAssessment) -> PermissionResult:
        """Show interactive permission dialog."""
        # Create future to capture dialog result
        result_future = asyncio.Future()
        
        def on_dialog_result(allowed: bool, always: bool):
            """Handle dialog result."""
            if always:
                # Save preference
                self.preferences.set_preference(tool_name, allowed)
                self.logger.info(f"Saved permission preference for {tool_name}: {allowed}")
            
            result = PermissionResult(allowed=allowed, always=always, assessment=assessment)
            result_future.set_result(result)
        
        # Create and show dialog
        dialog = PermissionDialog(
            tool_name=tool_name,
            parameters=parameters,
            assessment=assessment,
            callback=on_dialog_result
        )
        
        self.app.push_screen(dialog)
        
        # Wait for user decision
        return await result_future
    
    async def _show_blocked_dialog(self, tool_name: str, parameters: Dict[str, Any], assessment: RiskAssessment):
        """Show informational dialog for blocked operations."""
        # For now, just log and add a system message
        # Could be extended to show an informational modal
        message = f"🛡️ Blocked {tool_name}: {assessment.risk_level.value.upper()} risk operation"
        if hasattr(self.app, 'add_system_message'):
            self.app.add_system_message(message)
        else:
            self.logger.warning(message)
    
    def get_permission_status(self) -> Dict[str, Any]:
        """Get current permission system status."""
        return {
            "yolo_mode": self.yolo_mode,
            "preferences": self.preferences.get_summary(),
            "pending_requests": len(self._pending_requests),
            "permission_history": len(self.core_manager.permission_history)
        }
    
    def clear_preference(self, tool_name: str):
        """Clear permission preference for a tool."""
        self.preferences.clear_preference(tool_name)
        self.logger.info(f"Cleared permission preference for {tool_name}")
    
    def clear_all_preferences(self):
        """Clear all permission preferences."""
        self.preferences.clear_all()
        self.logger.info("Cleared all permission preferences")


class PermissionIntegrator:
    """Integrates permission checking into tool execution pipeline."""
    
    def __init__(self, permission_manager: TUIPermissionManager):
        self.permission_manager = permission_manager
        self.logger = get_main_logger()
    
    async def check_tool_permission(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Check permission for tool execution."""
        try:
            result = await self.permission_manager.request_permission(tool_name, parameters)
            
            if result.allowed:
                self.logger.debug(f"Permission granted for {tool_name}")
                return True
            else:
                self.logger.info(f"Permission denied for {tool_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Permission check failed for {tool_name}", error=str(e))
            # Fail safe - deny permission on error
            return False


# Global permission manager instance
_global_permission_manager: Optional[TUIPermissionManager] = None


def get_permission_manager() -> Optional[TUIPermissionManager]:
    """Get the global permission manager instance."""
    return _global_permission_manager


def set_permission_manager(manager: TUIPermissionManager):
    """Set the global permission manager instance."""
    global _global_permission_manager
    _global_permission_manager = manager


def get_permission_integrator() -> Optional[PermissionIntegrator]:
    """Get permission integrator if available."""
    manager = get_permission_manager()
    return PermissionIntegrator(manager) if manager else None