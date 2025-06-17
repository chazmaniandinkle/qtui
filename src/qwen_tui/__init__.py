"""
Qwen-TUI: A sophisticated terminal-based coding agent.

Combines Claude Code's proven UX patterns with Qwen3's powerful local inference capabilities.
"""

__version__ = "0.1.0"
__author__ = "Qwen-TUI Contributors"
__description__ = "Terminal-based coding agent with multi-backend LLM support"

from .config import Config, get_config, reload_config
from .logging import get_main_logger, configure_logging
from .exceptions import QwenTUIError

__all__ = [
    "__version__",
    "__author__", 
    "__description__",
    "Config",
    "get_config",
    "reload_config",
    "get_main_logger",
    "configure_logging",
    "QwenTUIError"
]