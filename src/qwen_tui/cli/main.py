"""
Main CLI entry point for Qwen-TUI.

Provides command-line interface with Rich console output and progress indicators.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import get_config, save_config, BackendType
from ..logging import configure_logging, get_main_logger, log_startup, log_shutdown
from ..exceptions import QwenTUIError
from . import setup, wizard

app = typer.Typer(
    name="qwen-tui",
    help="A sophisticated terminal-based coding agent with multi-backend LLM support.",
    add_completion=False,
    rich_markup_mode="rich"
)

backends_app = typer.Typer(name="backends", help="Backend management commands")
config_app = typer.Typer(name="config", help="Configuration management commands")
app.add_typer(backends_app, name="backends")
app.add_typer(config_app, name="config")

console = Console()


@app.callback()
def main(
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    log_level: Optional[str] = typer.Option(
        None, "--log-level", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Qwen-TUI: Terminal-based coding agent with multi-backend LLM support."""
    try:
        # Load configuration
        config = get_config()
        
        # Override log level if specified
        if log_level:
            config.logging.level = log_level.upper()
        if verbose:
            config.logging.level = "DEBUG"
        
        # Configure logging
        configure_logging(config.logging)
        
        # Log startup
        log_startup("0.1.0", str(config_file) if config_file else None)
        
    except Exception as e:
        console.print(f"[red]Error initializing Qwen-TUI: {e}[/red]")
        sys.exit(1)


@app.command()
def start(
    backend: Optional[str] = typer.Option(
        None, "--backend", "-b", help="Preferred backend to use"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Specific model to use"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Port for TUI server (if applicable)"
    ),
):
    """Start Qwen-TUI with automatic backend detection."""
    try:
        config = get_config()
        logger = get_main_logger()
        
        with console.status("[bold green]Starting Qwen-TUI..."):
            # Import here to avoid circular imports
            from ..backends.manager import BackendManager
            from ..tui.app import QwenTUIApp
            
            # Initialize backend manager
            backend_manager = BackendManager(config)
            
            # Override backend preference if specified
            if backend:
                try:
                    backend_type = BackendType(backend.lower())
                    config.preferred_backends = [backend_type]
                except ValueError:
                    available = [b.value for b in BackendType]
                    console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
                    raise typer.Exit(1)
            
            logger.info("Qwen-TUI starting", backend=backend, model=model)
            
            # Start the TUI application
            app_instance = QwenTUIApp(backend_manager, config)
            app_instance.run()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        log_shutdown()
    except QwenTUIError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        logger = get_main_logger()
        logger.error("Unexpected error during startup", error=str(e), error_type=type(e).__name__)
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


@backends_app.command("list")
def list_backends():
    """List all available backends and their status."""
    try:
        config = get_config()
        
        # Import here to avoid circular imports
        from ..backends.manager import BackendManager
        
        with console.status("[bold blue]Checking backends..."):
            backend_manager = BackendManager(config)
            
            # Get backend status
            results = asyncio.run(backend_manager.discover_backends())
        
        # Create status table
        table = Table(title="Available Backends")
        table.add_column("Backend", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Model", style="green")
        table.add_column("Host:Port", style="dim")
        table.add_column("Notes")
        
        for backend_type, status in results.items():
            if status["available"]:
                status_text = "[green]✓ Available[/green]"
                model = status.get("model", "N/A")
                host_port = f"{status.get('host', 'N/A')}:{status.get('port', 'N/A')}"
                notes = status.get("notes", "")
            else:
                status_text = "[red]✗ Unavailable[/red]"
                model = "N/A"
                host_port = "N/A"
                notes = status.get("error", "Unknown error")
            
            table.add_row(
                backend_type.value.title(),
                status_text,
                model,
                host_port,
                notes
            )
        
        console.print(table)
        
        # Show preferred order
        console.print("\n[bold]Preferred Backend Order:[/bold]")
        for i, backend in enumerate(config.preferred_backends, 1):
            console.print(f"  {i}. {backend.value.title()}")
            
    except Exception as e:
        console.print(f"[red]Error listing backends: {e}[/red]")
        sys.exit(1)


@backends_app.command("test")
def test_backends():
    """Test connectivity to all configured backends."""
    try:
        config = get_config()
        
        # Import here to avoid circular imports
        from ..backends.manager import BackendManager
        
        console.print("[bold blue]Testing backend connectivity...[/bold blue]\n")
        
        backend_manager = BackendManager(config)
        results = asyncio.run(backend_manager.test_all_backends())
        
        for backend_type, result in results.items():
            backend_name = backend_type.value.title()
            
            if result["success"]:
                console.print(f"[green]✓[/green] {backend_name}: {result['message']}")
                if "response_time" in result:
                    console.print(f"  Response time: {result['response_time']:.2f}s")
            else:
                console.print(f"[red]✗[/red] {backend_name}: {result['error']}")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error testing backends: {e}[/red]")
        sys.exit(1)


@backends_app.command("setup")
def setup_backend(
    backend: str = typer.Argument(..., help="Backend to setup (ollama, lm_studio, vllm, openrouter)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive setup")
):
    """Setup and configure a specific backend."""
    try:
        backend_type = BackendType(backend.lower())
    except ValueError:
        available = [b.value for b in BackendType]
        console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
        raise typer.Exit(1)
    
    try:
        if interactive:
            setup.interactive_backend_setup(backend_type)
        else:
            setup.automated_backend_setup(backend_type)
        
        console.print(f"[green]✓[/green] {backend.title()} setup completed!")
        
    except Exception as e:
        console.print(f"[red]Error setting up {backend}: {e}[/red]")
        sys.exit(1)


@config_app.command("show")
def show_config():
    """Show current configuration."""
    try:
        config = get_config()
        
        # Display configuration in panels
        console.print(Panel.fit(
            f"[bold]Preferred Backends:[/bold]\n" + 
            "\n".join(f"  • {b.value}" for b in config.preferred_backends),
            title="Backend Configuration"
        ))
        
        console.print(Panel.fit(
            f"[bold]Log Level:[/bold] {config.logging.level.value}\n" +
            f"[bold]Log Format:[/bold] {config.logging.format}\n" +
            f"[bold]Log File:[/bold] {config.logging.file or 'Console only'}",
            title="Logging Configuration"
        ))
        
        console.print(Panel.fit(
            f"[bold]Security Profile:[/bold] {config.security.profile.value}\n" +
            f"[bold]Allow File Write:[/bold] {config.security.allow_file_write}\n" +
            f"[bold]Allow File Delete:[/bold] {config.security.allow_file_delete}\n" +
            f"[bold]Allow Network:[/bold] {config.security.allow_network}",
            title="Security Configuration"
        ))
        
    except Exception as e:
        console.print(f"[red]Error showing configuration: {e}[/red]")
        sys.exit(1)


@config_app.command("init")
def init_config(
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration")
):
    """Initialize default configuration file."""
    try:
        wizard.run_config_wizard(force=force)
        console.print("[green]✓[/green] Configuration initialized!")
        
    except Exception as e:
        console.print(f"[red]Error initializing configuration: {e}[/red]")
        sys.exit(1)


@app.command()
def version():
    """Show version information."""
    console.print(Panel.fit(
        "[bold cyan]Qwen-TUI[/bold cyan] v0.1.0\n\n" +
        "A sophisticated terminal-based coding agent\n" +
        "combining Claude Code UX patterns with Qwen3's\n" +
        "powerful local inference capabilities.\n\n" +
        "[dim]Built with ❤️ for developers[/dim]",
        title="Version Information"
    ))


def main_entry():
    """Entry point for the CLI application."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()