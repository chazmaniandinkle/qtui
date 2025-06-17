"""
Configuration wizard for Qwen-TUI.

Provides interactive configuration setup with guided workflows
and intelligent defaults.
"""
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from ..config import (
    Config, BackendType, SecurityProfile, LogLevel,
    get_config_paths, save_config
)
from .setup import detect_available_backends, suggest_qwen_models

console = Console()


def run_config_wizard(force: bool = False) -> None:
    """Run the interactive configuration wizard."""
    console.print(Panel.fit(
        "[bold cyan]Qwen-TUI Configuration Wizard[/bold cyan]\n\n" +
        "This wizard will help you set up Qwen-TUI with your preferred backends\n" +
        "and security settings. You can always modify the configuration later.",
        title="Welcome"
    ))
    
    # Check if config already exists
    existing_config_path = None
    for path in get_config_paths():
        if path.exists():
            existing_config_path = path
            break
    
    if existing_config_path and not force:
        console.print(f"\n[yellow]Configuration file already exists at: {existing_config_path}[/yellow]")
        if not Confirm.ask("Do you want to overwrite it?"):
            console.print("Configuration wizard cancelled.")
            return
    
    # Start with default configuration
    config = Config()
    
    # Backend configuration
    configure_backends(config)
    
    # Security configuration
    configure_security(config)
    
    # Logging configuration
    configure_logging(config)
    
    # UI configuration
    configure_ui(config)
    
    # Advanced settings
    if Confirm.ask("\nWould you like to configure advanced settings?", default=False):
        configure_advanced(config)
    
    # Save configuration
    save_location = choose_save_location()
    save_config(config, save_location)
    
    console.print(f"\n[green]✓[/green] Configuration saved to: {save_location}")
    console.print("\nYou can now start Qwen-TUI with: [bold]qwen-tui start[/bold]")


def configure_backends(config: Config) -> None:
    """Configure backend preferences and settings."""
    console.print("\n[bold blue]Backend Configuration[/bold blue]")
    
    # Detect available backends
    console.print("Detecting available backends...")
    available_backends = detect_available_backends()
    
    # Show detection results
    table = Table(title="Backend Detection Results")
    table.add_column("Backend", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Notes")
    
    available_list = []
    for backend_type, status in available_backends.items():
        if status["available"]:
            table.add_row(
                backend_type.value.title(),
                "[green]✓ Available[/green]",
                "Ready to use"
            )
            available_list.append(backend_type)
        else:
            table.add_row(
                backend_type.value.title(),
                "[red]✗ Not Available[/red]",
                "Needs setup"
            )
    
    console.print(table)
    
    if not available_list:
        console.print("\n[yellow]No backends are currently available.[/yellow]")
        console.print("You'll need to set up at least one backend before using Qwen-TUI.")
        console.print("Run: [bold]qwen-tui backends setup <backend_name>[/bold]")
        return
    
    # Configure backend preferences
    console.print("\n[bold]Backend Preferences[/bold]")
    console.print("Choose your preferred backend order (most preferred first):")
    
    preferred_backends = []
    remaining_backends = available_list.copy()
    
    while remaining_backends:
        console.print(f"\nAvailable backends:")
        for i, backend in enumerate(remaining_backends, 1):
            console.print(f"  {i}. {backend.value.title()}")
        
        if len(preferred_backends) > 0:
            console.print(f"  {len(remaining_backends) + 1}. Done")
        
        try:
            choice = IntPrompt.ask(
                f"Select backend #{len(preferred_backends) + 1} (or Done)",
                choices=[str(i) for i in range(1, len(remaining_backends) + 2)]
            )
            
            if choice <= len(remaining_backends):
                selected = remaining_backends[choice - 1]
                preferred_backends.append(selected)
                remaining_backends.remove(selected)
                console.print(f"Added {selected.value.title()} to preferences")
            else:
                break
                
        except (ValueError, KeyboardInterrupt):
            break
    
    if preferred_backends:
        config.preferred_backends = preferred_backends
        console.print(f"\n[green]✓[/green] Backend preferences configured")
        console.print("Order:", " → ".join(b.value.title() for b in preferred_backends))


def configure_security(config: Config) -> None:
    """Configure security settings."""
    console.print("\n[bold blue]Security Configuration[/bold blue]")
    
    # Security profile
    console.print("\nSecurity profiles:")
    console.print("  1. [red]strict[/red]    - Maximum security, requires approval for most operations")
    console.print("  2. [yellow]balanced[/yellow]  - Good security with reasonable convenience (recommended)")
    console.print("  3. [green]permissive[/green] - Minimal restrictions, faster workflow")
    
    profile_choice = Prompt.ask(
        "Security profile",
        choices=["strict", "balanced", "permissive"],
        default="balanced"
    )
    config.security.profile = SecurityProfile(profile_choice)
    
    # File operation permissions
    if Confirm.ask("Allow file write operations?", default=True):
        config.security.allow_file_write = True
    
    if Confirm.ask("Allow file delete operations?", default=False):
        config.security.allow_file_delete = True
    
    if Confirm.ask("Allow network operations?", default=True):
        config.security.allow_network = True
    
    console.print(f"[green]✓[/green] Security configured with {profile_choice} profile")


def configure_logging(config: Config) -> None:
    """Configure logging settings."""
    console.print("\n[bold blue]Logging Configuration[/bold blue]")
    
    # Log level
    log_level = Prompt.ask(
        "Log level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO"
    )
    config.logging.level = LogLevel(log_level)
    
    # Log format
    log_format = Prompt.ask(
        "Log format",
        choices=["human", "json"],
        default="human"
    )
    config.logging.format = log_format
    
    # Log file
    if Confirm.ask("Save logs to file?", default=False):
        default_path = str(Path.home() / ".cache" / "qwen-tui" / "qwen-tui.log")
        log_file = Prompt.ask("Log file path", default=default_path)
        config.logging.file = log_file
    
    console.print(f"[green]✓[/green] Logging configured")


def configure_ui(config: Config) -> None:
    """Configure UI preferences."""
    console.print("\n[bold blue]UI Configuration[/bold blue]")
    
    # Theme
    theme = Prompt.ask(
        "UI theme",
        choices=["dark", "light"],
        default="dark"
    )
    config.ui.theme = theme
    
    # UI preferences
    config.ui.show_typing_indicator = Confirm.ask("Show typing indicator?", default=True)
    config.ui.auto_scroll = Confirm.ask("Auto-scroll chat?", default=True)
    
    # Font size
    font_size = Prompt.ask(
        "Font size",
        choices=["small", "normal", "large"],
        default="normal"
    )
    config.ui.font_size = font_size
    
    console.print(f"[green]✓[/green] UI configured with {theme} theme")


def configure_advanced(config: Config) -> None:
    """Configure advanced settings."""
    console.print("\n[bold blue]Advanced Configuration[/bold blue]")
    
    # Context settings
    if Confirm.ask("Configure context window settings?", default=False):
        max_tokens = IntPrompt.ask(
            "Maximum context tokens",
            default=config.max_context_tokens
        )
        config.max_context_tokens = max_tokens
    
    # Performance settings
    if Confirm.ask("Configure performance settings?", default=False):
        parallel_tools = IntPrompt.ask(
            "Maximum parallel tool executions",
            default=config.parallel_tools
        )
        config.parallel_tools = parallel_tools
        
        config.cache_responses = Confirm.ask(
            "Cache LLM responses?",
            default=config.cache_responses
        )
    
    console.print("[green]✓[/green] Advanced settings configured")


def choose_save_location() -> Path:
    """Choose where to save the configuration file."""
    console.print("\n[bold blue]Save Location[/bold blue]")
    
    # Suggest default locations
    suggestions = [
        Path.cwd() / "qwen-tui.yaml",  # Current directory
        Path.home() / ".config" / "qwen-tui" / "config.yaml",  # User config
    ]
    
    console.print("Suggested locations:")
    for i, path in enumerate(suggestions, 1):
        console.print(f"  {i}. {path}")
    console.print(f"  {len(suggestions) + 1}. Custom path")
    
    try:
        choice = IntPrompt.ask(
            "Save location",
            choices=[str(i) for i in range(1, len(suggestions) + 2)],
            default="2"
        )
        
        if choice <= len(suggestions):
            selected_path = suggestions[choice - 1]
        else:
            custom_path = Prompt.ask("Enter custom path")
            selected_path = Path(custom_path)
        
        # Create directory if it doesn't exist
        selected_path.parent.mkdir(parents=True, exist_ok=True)
        
        return selected_path
        
    except (ValueError, KeyboardInterrupt):
        return suggestions[1]  # Default to user config directory


def quick_setup() -> None:
    """Quick setup with sensible defaults."""
    console.print(Panel.fit(
        "[bold cyan]Quick Setup[/bold cyan]\n\n" +
        "This will create a configuration with sensible defaults\n" +
        "based on your available backends.",
        title="Quick Setup"
    ))
    
    config = Config()
    
    # Auto-detect and configure backends
    available_backends = detect_available_backends()
    available_list = [bt for bt, status in available_backends.items() if status["available"]]
    
    if available_list:
        config.preferred_backends = available_list
        console.print(f"[green]✓[/green] Auto-configured backends: {', '.join(b.value for b in available_list)}")
    else:
        console.print("[yellow]No backends detected. Please run backend setup first.[/yellow]")
        return
    
    # Use balanced defaults
    config.security.profile = SecurityProfile.BALANCED
    config.logging.level = LogLevel.INFO
    config.ui.theme = "dark"
    
    # Save to user config directory
    config_dir = Path.home() / ".config" / "qwen-tui"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    
    save_config(config, config_path)
    
    console.print(f"[green]✓[/green] Quick setup complete! Configuration saved to: {config_path}")
    console.print("You can now start Qwen-TUI with: [bold]qwen-tui start[/bold]")