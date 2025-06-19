"""
Logging infrastructure for Qwen-TUI.

Provides structured logging with correlation IDs, multiple output formats,
and backend-specific log channels.
"""
import logging
import logging.handlers
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar

import structlog

from .config import LoggingConfig, LogLevel


# Context variable for correlation ID tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIDProcessor:
    """Add correlation ID to log records."""
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add correlation ID to the event dictionary."""
        if cid := correlation_id.get():
            event_dict['correlation_id'] = cid
        return event_dict


class BackendProcessor:
    """Add backend information to log records."""
    
    def __init__(self, backend_name: Optional[str] = None):
        self.backend_name = backend_name
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add backend name to the event dictionary."""
        if self.backend_name:
            event_dict['backend'] = self.backend_name
        return event_dict


def setup_logging(config: LoggingConfig, tui_mode: bool = False) -> None:
    """Setup structured logging based on configuration."""
    # Clear any existing structlog configuration
    structlog.reset_defaults()
    
    # Configure standard library logging
    # In TUI mode, don't use stdout to avoid interfering with the TUI
    if tui_mode:
        # In TUI mode, ensure we have a log file
        if not config.file:
            # Create a default log file for TUI mode
            import tempfile
            import os
            log_dir = os.path.join(tempfile.gettempdir(), "qwen-tui")
            os.makedirs(log_dir, exist_ok=True)
            config.file = os.path.join(log_dir, "qwen-tui.log")
        
        # Don't configure console logging in TUI mode
        # Install a NullHandler so Textual doesn't add its own handler
        logging.basicConfig(
            format="%(message)s",
            level=getattr(logging, config.level.value),
            handlers=[],  # No handlers for stdout in TUI mode
            force=True,   # Remove existing handlers
        )
    else:
        # Normal CLI mode - use stdout
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, config.level.value),
            force=True,
        )
    
    # Setup file logging if specified
    if config.file:
        file_path = Path(config.file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to manage log file size
        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.file,
            maxBytes=config.max_size,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, config.level.value))
        
        # Attach file handler to the root logger so all logs are captured
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(getattr(logging, config.level.value))
    
    # Configure processors based on format
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        CorrelationIDProcessor(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None, backend: Optional[str] = None) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    if name is None:
        name = "qwen_tui"
    
    logger = structlog.get_logger(name)
    
    if backend:
        logger = logger.bind(backend=backend)
    
    return logger


@contextmanager
def log_context(
    correlation_id_value: Optional[str] = None,
    **context_data: Any
):
    """
    Context manager for adding correlation ID and additional context to logs.
    
    Args:
        correlation_id_value: Correlation ID to use. If None, generates a new UUID.
        **context_data: Additional context data to include in logs.
    """
    if correlation_id_value is None:
        correlation_id_value = str(uuid.uuid4())[:8]
    
    # Set correlation ID in context variable
    token = correlation_id.set(correlation_id_value)
    
    # Get logger with context
    logger = get_logger().bind(**context_data)
    
    try:
        yield logger
    finally:
        # Reset correlation ID
        correlation_id.reset(token)


def log_backend_operation(backend_name: str, operation: str, **kwargs: Any):
    """
    Decorator/context manager for logging backend operations.
    
    Args:
        backend_name: Name of the backend
        operation: Operation being performed
        **kwargs: Additional context data
    """
    def decorator(func):
        def wrapper(*args, **func_kwargs):
            with log_context(backend=backend_name, operation=operation, **kwargs) as logger:
                logger.info("Starting backend operation", 
                           operation=operation, 
                           backend=backend_name)
                try:
                    result = func(*args, **func_kwargs)
                    logger.info("Backend operation completed successfully",
                               operation=operation,
                               backend=backend_name)
                    return result
                except Exception as e:
                    logger.error("Backend operation failed",
                                operation=operation,
                                backend=backend_name,
                                error=str(e),
                                error_type=type(e).__name__)
                    raise
        return wrapper
    return decorator


class QwenTUILogger:
    """
    Specialized logger for Qwen-TUI with convenience methods.
    """
    
    def __init__(self, name: str = "qwen_tui", backend: Optional[str] = None):
        self.name = name
        self.backend = backend
        self._logger = get_logger(name, backend)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._logger.critical(message, **kwargs)
    
    def log_request(self, request_data: Dict[str, Any]) -> None:
        """Log LLM request."""
        self._logger.info("LLM request sent",
                         backend=self.backend,
                         request_type="llm_request",
                         token_count=len(str(request_data).split()),
                         has_tools=bool(request_data.get("tools")))
    
    def log_response(self, response_data: Dict[str, Any]) -> None:
        """Log LLM response."""
        self._logger.info("LLM response received",
                         backend=self.backend,
                         request_type="llm_response",
                         has_content=bool(response_data.get("content")),
                         has_tool_calls=bool(response_data.get("tool_calls")),
                         usage=response_data.get("usage", {}))
    
    def log_tool_execution(self, tool_name: str, args: Dict[str, Any], success: bool, duration: float) -> None:
        """Log tool execution."""
        self._logger.info("Tool execution completed",
                         tool_name=tool_name,
                         success=success,
                         duration=duration,
                         request_type="tool_execution")
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error with additional context."""
        self._logger.error("Error occurred",
                          error=str(error),
                          error_type=type(error).__name__,
                          **context)
    
    def log_performance_metric(self, metric_name: str, value: Union[int, float], unit: str = "") -> None:
        """Log performance metric."""
        self._logger.info("Performance metric",
                         metric_name=metric_name,
                         value=value,
                         unit=unit,
                         request_type="performance_metric")
    
    def with_context(self, **context: Any) -> 'QwenTUILogger':
        """Create a new logger with additional context."""
        new_logger = QwenTUILogger(self.name, self.backend)
        new_logger._logger = self._logger.bind(**context)
        return new_logger


# Global logger instances
_main_logger: Optional[QwenTUILogger] = None
_backend_loggers: Dict[str, QwenTUILogger] = {}


def get_main_logger() -> QwenTUILogger:
    """Get the main application logger."""
    global _main_logger
    if _main_logger is None:
        _main_logger = QwenTUILogger("qwen_tui")
    return _main_logger


def get_backend_logger(backend_name: str) -> QwenTUILogger:
    """Get a backend-specific logger."""
    global _backend_loggers
    if backend_name not in _backend_loggers:
        _backend_loggers[backend_name] = QwenTUILogger(f"qwen_tui.{backend_name}", backend_name)
    return _backend_loggers[backend_name]


def configure_logging(config: LoggingConfig, tui_mode: bool = False) -> None:
    """Configure logging system with the provided configuration."""
    setup_logging(config, tui_mode)
    
    # Log configuration
    logger = get_main_logger()
    logger.info("Logging system configured",
               level=config.level.value,
               format=config.format,
               file=config.file)


# Convenience functions for common logging patterns
def log_startup(version: str, config_path: Optional[str] = None) -> None:
    """Log application startup."""
    logger = get_main_logger()
    with log_context() as ctx_logger:
        ctx_logger.info("Qwen-TUI starting up",
                       version=version,
                       config_path=config_path,
                       request_type="startup")


def log_shutdown() -> None:
    """Log application shutdown."""
    logger = get_main_logger()
    with log_context() as ctx_logger:
        ctx_logger.info("Qwen-TUI shutting down",
                       request_type="shutdown")


def log_backend_discovery(backends_found: list, backends_available: list) -> None:
    """Log backend discovery results."""
    logger = get_main_logger()
    logger.info("Backend discovery completed",
               backends_found=backends_found,
               backends_available=backends_available,
               request_type="backend_discovery")