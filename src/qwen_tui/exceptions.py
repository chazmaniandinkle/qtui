"""
Custom exception hierarchy for Qwen-TUI.

Provides specific exceptions for different error conditions with
helpful error messages and context information.
"""
from typing import Any, Dict, Optional, Union


class QwenTUIError(Exception):
    """Base exception for all Qwen-TUI errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.context = context or {}
        self.cause = cause
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


# Configuration Errors
class ConfigurationError(QwenTUIError):
    """Error in configuration loading or validation."""
    pass


class InvalidConfigError(ConfigurationError):
    """Configuration file is invalid or malformed."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""
    pass


# Backend Errors
class BackendError(QwenTUIError):
    """Base class for backend-related errors."""
    
    def __init__(
        self,
        message: str,
        backend_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.backend_name = backend_name
        context = context or {}
        if backend_name:
            context["backend"] = backend_name
        super().__init__(message, context, cause)


class BackendUnavailableError(BackendError):
    """Backend is not available or cannot be reached."""
    pass


class BackendConnectionError(BackendError):
    """Error connecting to backend service."""
    pass


class BackendTimeoutError(BackendError):
    """Backend request timed out."""
    pass


class BackendAuthenticationError(BackendError):
    """Authentication failed with backend."""
    pass


class BackendRateLimitError(BackendError):
    """Backend rate limit exceeded."""
    pass


class InvalidBackendResponseError(BackendError):
    """Backend returned invalid or unexpected response."""
    pass


class UnsupportedBackendError(BackendError):
    """Backend type is not supported."""
    pass


# LLM Errors
class LLMError(QwenTUIError):
    """Base class for LLM-related errors."""
    pass


class LLMGenerationError(LLMError):
    """Error during LLM text generation."""
    pass


class LLMToolCallError(LLMError):
    """Error in LLM tool calling."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.tool_name = tool_name
        context = context or {}
        if tool_name:
            context["tool"] = tool_name
        super().__init__(message, context, cause)


class InvalidToolCallError(LLMToolCallError):
    """Tool call is invalid or malformed."""
    pass


class ToolExecutionError(LLMToolCallError):
    """Error executing tool call."""
    pass


# Security Errors
class SecurityError(QwenTUIError):
    """Base class for security-related errors."""
    pass


class PermissionDeniedError(SecurityError):
    """Operation denied by security policy."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        risk_level: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.operation = operation
        self.risk_level = risk_level
        context = context or {}
        if operation:
            context["operation"] = operation
        if risk_level:
            context["risk_level"] = risk_level
        super().__init__(message, context, cause)


class UnsafeOperationError(SecurityError):
    """Operation is considered unsafe."""
    pass


class SecurityPolicyViolationError(SecurityError):
    """Operation violates security policy."""
    pass


# Tool Errors
class ToolError(QwenTUIError):
    """Base class for tool-related errors."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.tool_name = tool_name
        context = context or {}
        if tool_name:
            context["tool"] = tool_name
        super().__init__(message, context, cause)


class ToolNotFoundError(ToolError):
    """Requested tool is not found or available."""
    pass


class ToolInitializationError(ToolError):
    """Error initializing tool."""
    pass


class ToolParameterError(ToolError):
    """Invalid parameters provided to tool."""
    pass


class FileSystemError(ToolError):
    """File system operation error."""
    
    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.path = path
        self.operation = operation
        context = context or {}
        if path:
            context["path"] = path
        if operation:
            context["operation"] = operation
        super().__init__(message, "filesystem", context, cause)


class ShellExecutionError(ToolError):
    """Shell command execution error."""
    
    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.command = command
        self.exit_code = exit_code
        context = context or {}
        if command:
            context["command"] = command
        if exit_code is not None:
            context["exit_code"] = exit_code
        super().__init__(message, "shell", context, cause)


# TUI Errors
class TUIError(QwenTUIError):
    """Base class for TUI-related errors."""
    pass


class TUIInitializationError(TUIError):
    """Error initializing TUI."""
    pass


class TUIRenderError(TUIError):
    """Error rendering TUI component."""
    pass


class KeyBindingError(TUIError):
    """Error with key binding configuration."""
    pass


# MCP Errors
class MCPError(QwenTUIError):
    """Base class for MCP-related errors."""
    pass


class MCPConnectionError(MCPError):
    """Error connecting to MCP server."""
    pass


class MCPProtocolError(MCPError):
    """MCP protocol error."""
    pass


class MCPServerError(MCPError):
    """MCP server error."""
    pass


# Context Manager for Error Handling
class ErrorContext:
    """Context manager for consistent error handling."""
    
    def __init__(
        self,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        reraise_as: Optional[type] = None
    ):
        self.operation = operation
        self.context = context or {}
        self.reraise_as = reraise_as
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        
        # Don't re-wrap Qwen-TUI exceptions
        if isinstance(exc_val, QwenTUIError):
            return False
        
        # Wrap in specified exception type or generic QwenTUIError
        if self.reraise_as:
            raise self.reraise_as(
                f"Error in {self.operation}: {exc_val}",
                context=self.context,
                cause=exc_val
            ) from exc_val
        else:
            raise QwenTUIError(
                f"Error in {self.operation}: {exc_val}",
                context=self.context,
                cause=exc_val
            ) from exc_val


def handle_backend_error(
    error: Exception,
    backend_name: str,
    operation: str
) -> BackendError:
    """Convert generic exceptions to appropriate backend errors."""
    context = {"operation": operation}
    
    if isinstance(error, ConnectionError):
        return BackendConnectionError(
            f"Failed to connect to {backend_name}",
            backend_name=backend_name,
            context=context,
            cause=error
        )
    elif isinstance(error, TimeoutError):
        return BackendTimeoutError(
            f"Request to {backend_name} timed out",
            backend_name=backend_name,
            context=context,
            cause=error
        )
    elif "authentication" in str(error).lower() or "unauthorized" in str(error).lower():
        return BackendAuthenticationError(
            f"Authentication failed with {backend_name}",
            backend_name=backend_name,
            context=context,
            cause=error
        )
    elif "rate limit" in str(error).lower():
        return BackendRateLimitError(
            f"Rate limit exceeded for {backend_name}",
            backend_name=backend_name,
            context=context,
            cause=error
        )
    else:
        return BackendError(
            f"Error communicating with {backend_name}: {error}",
            backend_name=backend_name,
            context=context,
            cause=error
        )


def format_error_for_user(error: Exception) -> str:
    """Format error message for display to user."""
    if isinstance(error, QwenTUIError):
        return str(error)
    else:
        return f"Unexpected error: {error}"


def get_error_details(error: Exception) -> Dict[str, Any]:
    """Extract detailed error information for logging."""
    details = {
        "error_type": type(error).__name__,
        "message": str(error),
    }
    
    if isinstance(error, QwenTUIError):
        details.update({
            "context": error.context,
            "cause": str(error.cause) if error.cause else None,
        })
        
        # Add specific fields for different error types
        if isinstance(error, BackendError) and error.backend_name:
            details["backend"] = error.backend_name
        elif isinstance(error, ToolError) and error.tool_name:
            details["tool"] = error.tool_name
        elif isinstance(error, PermissionDeniedError):
            if error.operation:
                details["operation"] = error.operation
            if error.risk_level:
                details["risk_level"] = error.risk_level
    
    return details