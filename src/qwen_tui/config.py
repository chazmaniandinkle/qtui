"""
Configuration management for Qwen-TUI.

Provides type-safe configuration loading from YAML/TOML files and environment variables.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator
import yaml


class LogLevel(str, Enum):
    """Logging level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BackendType(str, Enum):
    """Available LLM backends."""
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    VLLM = "vllm"
    OPENROUTER = "openrouter"


class SecurityProfile(str, Enum):
    """Security permission profiles."""
    STRICT = "strict"
    BALANCED = "balanced"
    PERMISSIVE = "permissive"
    CUSTOM = "custom"


class OllamaConfig(BaseModel):
    """Ollama backend configuration."""
    host: str = Field(default="localhost", description="Ollama host")
    port: int = Field(default=11434, description="Ollama port")
    model: str = Field(default="qwen2.5-coder:latest", description="Default model")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    keep_alive: Union[int, str] = Field(default="5m", description="Model keep alive time")


class LMStudioConfig(BaseModel):
    """LM Studio backend configuration."""
    host: str = Field(default="localhost", description="LM Studio host")
    port: int = Field(default=1234, description="LM Studio port")
    api_key: Optional[str] = Field(default=None, description="API key if required")
    timeout: int = Field(default=300, description="Request timeout in seconds")


class VLLMConfig(BaseModel):
    """vLLM backend configuration."""
    host: str = Field(default="localhost", description="vLLM host")
    port: int = Field(default=8000, description="vLLM port")
    model: str = Field(default="Qwen/Qwen2.5-Coder-7B-Instruct", description="Model path")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    max_tokens: int = Field(default=4096, description="Maximum tokens per request")
    temperature: float = Field(default=0.1, description="Generation temperature")


class OpenRouterConfig(BaseModel):
    """OpenRouter backend configuration."""
    api_key: str = Field(..., description="OpenRouter API key")
    model: str = Field(default="qwen/qwen-2.5-coder-32b-instruct", description="Model to use")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API base URL")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    format: str = Field(default="human", description="Log format: human, json")
    file: Optional[str] = Field(default=None, description="Log file path")
    max_size: int = Field(default=10_000_000, description="Max log file size in bytes")
    backup_count: int = Field(default=5, description="Number of backup files to keep")


class SecurityConfig(BaseModel):
    """Security and permissions configuration."""
    profile: SecurityProfile = Field(default=SecurityProfile.BALANCED, description="Security profile")
    allowed_commands: List[str] = Field(default_factory=list, description="Allowed shell commands")
    blocked_commands: List[str] = Field(default_factory=list, description="Blocked shell commands")
    allow_network: bool = Field(default=True, description="Allow network operations")
    allow_file_write: bool = Field(default=True, description="Allow file write operations")
    allow_file_delete: bool = Field(default=False, description="Allow file delete operations")
    require_approval_for: List[str] = Field(
        default_factory=lambda: ["file_delete", "shell_exec", "network_request"],
        description="Operations requiring user approval"
    )


class UIConfig(BaseModel):
    """TUI configuration."""
    theme: str = Field(default="dark", description="UI theme")
    animation_speed: float = Field(default=1.0, description="Animation speed multiplier")
    show_typing_indicator: bool = Field(default=True, description="Show typing indicator")
    auto_scroll: bool = Field(default=True, description="Auto-scroll chat")
    font_size: str = Field(default="normal", description="Font size: small, normal, large")


class Config(BaseModel):
    """Main configuration model."""
    # Backend configurations
    preferred_backends: List[BackendType] = Field(
        default_factory=lambda: [BackendType.OLLAMA, BackendType.LM_STUDIO],
        description="Preferred backend order"
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    lm_studio: LMStudioConfig = Field(default_factory=LMStudioConfig)
    vllm: VLLMConfig = Field(default_factory=VLLMConfig)
    openrouter: OpenRouterConfig = Field(default_factory=lambda: OpenRouterConfig(api_key=""))
    
    # System configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    
    # Advanced settings
    max_context_tokens: int = Field(default=32000, description="Maximum context window")
    parallel_tools: int = Field(default=3, description="Maximum parallel tool executions")
    cache_responses: bool = Field(default=True, description="Cache LLM responses")
    
    @field_validator('openrouter')
    @classmethod
    def validate_openrouter_api_key(cls, v):
        """Validate OpenRouter API key if backend is enabled."""
        if v.api_key == "":
            # Set from environment if available
            v.api_key = os.getenv("OPENROUTER_API_KEY", "")
        return v


def get_config_paths() -> List[Path]:
    """Get possible configuration file paths in order of preference."""
    paths = []
    
    # Current directory
    for ext in ['yaml', 'yml', 'toml']:
        paths.append(Path(f"qwen-tui.{ext}"))
        paths.append(Path(f"config.{ext}"))
    
    # User config directory
    if config_home := os.getenv("XDG_CONFIG_HOME"):
        config_dir = Path(config_home) / "qwen-tui"
    else:
        config_dir = Path.home() / ".config" / "qwen-tui"
    
    for ext in ['yaml', 'yml', 'toml']:
        paths.append(config_dir / f"config.{ext}")
    
    # System config directory
    for ext in ['yaml', 'yml', 'toml']:
        paths.append(Path(f"/etc/qwen-tui/config.{ext}"))
    
    return paths


def load_config() -> Config:
    """Load configuration from files and environment variables."""
    config_data = {}
    
    # Try to load from config files
    for config_path in get_config_paths():
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    if config_path.suffix in ['.yaml', '.yml']:
                        file_config = yaml.safe_load(f) or {}
                    else:  # .toml
                        try:
                            import tomllib  # Python 3.11+
                        except ImportError:
                            import tomli as tomllib  # Fallback for older Python
                        
                        with open(config_path, 'rb') as tf:
                            file_config = tomllib.load(tf)
                    
                    config_data.update(file_config)
                    break
            except yaml.YAMLError as e:
                # YAML parsing error
                print(f"Warning: Invalid YAML syntax in {config_path}: {e}")
                print("Using default configuration instead.")
            except FileNotFoundError:
                # File disappeared between exists check and open
                print(f"Warning: Config file {config_path} not found (may have been removed)")
            except PermissionError:
                # No read permission
                print(f"Warning: No permission to read config file {config_path}")
            except Exception as e:
                # Other unexpected errors
                print(f"Warning: Failed to load config from {config_path}: {e}")
                print("Using default configuration instead.")
    
    # Override with environment variables
    env_overrides = {}
    
    # Backend preferences
    if backends := os.getenv("QWEN_TUI_BACKENDS"):
        env_overrides["preferred_backends"] = backends.split(",")
    
    # Ollama settings
    if ollama_host := os.getenv("QWEN_TUI_OLLAMA_HOST"):
        env_overrides.setdefault("ollama", {})["host"] = ollama_host
    if ollama_port := os.getenv("QWEN_TUI_OLLAMA_PORT"):
        try:
            env_overrides.setdefault("ollama", {})["port"] = int(ollama_port)
        except ValueError:
            print(f"Warning: Invalid port number in QWEN_TUI_OLLAMA_PORT: {ollama_port}")
            print("Using default port instead.")
    if ollama_model := os.getenv("QWEN_TUI_OLLAMA_MODEL"):
        env_overrides.setdefault("ollama", {})["model"] = ollama_model
    
    # LM Studio settings
    if lm_host := os.getenv("QWEN_TUI_LM_STUDIO_HOST"):
        env_overrides.setdefault("lm_studio", {})["host"] = lm_host
    if lm_port := os.getenv("QWEN_TUI_LM_STUDIO_PORT"):
        try:
            env_overrides.setdefault("lm_studio", {})["port"] = int(lm_port)
        except ValueError:
            print(f"Warning: Invalid port number in QWEN_TUI_LM_STUDIO_PORT: {lm_port}")
            print("Using default port instead.")
    
    # vLLM settings
    if vllm_host := os.getenv("QWEN_TUI_VLLM_HOST"):
        env_overrides.setdefault("vllm", {})["host"] = vllm_host
    if vllm_port := os.getenv("QWEN_TUI_VLLM_PORT"):
        try:
            env_overrides.setdefault("vllm", {})["port"] = int(vllm_port)
        except ValueError:
            print(f"Warning: Invalid port number in QWEN_TUI_VLLM_PORT: {vllm_port}")
            print("Using default port instead.")
    if vllm_model := os.getenv("QWEN_TUI_VLLM_MODEL"):
        env_overrides.setdefault("vllm", {})["model"] = vllm_model
    
    # OpenRouter settings
    if openrouter_key := os.getenv("OPENROUTER_API_KEY"):
        env_overrides.setdefault("openrouter", {})["api_key"] = openrouter_key
    if openrouter_model := os.getenv("QWEN_TUI_OPENROUTER_MODEL"):
        env_overrides.setdefault("openrouter", {})["model"] = openrouter_model
    
    # Logging settings
    if log_level := os.getenv("QWEN_TUI_LOG_LEVEL"):
        env_overrides.setdefault("logging", {})["level"] = log_level.upper()
    if log_file := os.getenv("QWEN_TUI_LOG_FILE"):
        env_overrides.setdefault("logging", {})["file"] = log_file
    
    # Security settings
    if security_profile := os.getenv("QWEN_TUI_SECURITY_PROFILE"):
        env_overrides.setdefault("security", {})["profile"] = security_profile
    
    # Merge configurations: defaults < file < environment
    final_config = {**config_data, **env_overrides}
    
    try:
        return Config(**final_config)
    except Exception as e:
        print(f"Error: Invalid configuration data: {e}")
        print("Using default configuration. Please check your config file and environment variables.")
        # Return default config as fallback
        return Config()


def save_config(config: Config, path: Optional[Path] = None) -> None:
    """Save configuration to file."""
    if path is None:
        # Use user config directory
        if config_home := os.getenv("XDG_CONFIG_HOME"):
            config_dir = Path(config_home) / "qwen-tui"
        else:
            config_dir = Path.home() / ".config" / "qwen-tui"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "config.yaml"
    
    # Convert to dict and handle enum serialization
    config_dict = config.model_dump()
    
    # Convert enum values to strings for YAML serialization
    def convert_enums(obj):
        if isinstance(obj, dict):
            return {k: convert_enums(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_enums(item) for item in obj]
        elif hasattr(obj, 'value'):  # Enum
            return obj.value
        else:
            return obj
    
    config_dict = convert_enums(config_dict)
    
    with open(path, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """Reload configuration from files."""
    global _config
    _config = load_config()
    return _config