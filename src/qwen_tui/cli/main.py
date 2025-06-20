"""
Main CLI entry point for Qwen-TUI.

Provides command-line interface with Rich console output and progress indicators.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

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
models_app = typer.Typer(name="models", help="Model management and selection commands")
app.add_typer(backends_app, name="backends")
app.add_typer(config_app, name="config")
app.add_typer(models_app, name="models")

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
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Qwen-TUI: Terminal-based coding agent with multi-backend LLM support."""
    try:
        # Load configuration
        config = get_config()
        
        # Override log level if specified
        if log_level:
            config.logging.level = log_level.upper()
        if verbose or debug:
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
        
        # Reconfigure logging for TUI mode BEFORE any backend initialization
        configure_logging(config.logging, tui_mode=True)
        
        with console.status("[bold green]Starting Qwen-TUI..."):
            # Import here to avoid circular imports
            from ..backends.manager import BackendManager
            from ..tui.app import QwenTUIApp
            
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
            
            # Initialize backend manager (now with TUI-safe logging)
            backend_manager = BackendManager(config)
            
            # Start the TUI application
            app_instance = QwenTUIApp(backend_manager, config)
            app_instance.run()
            
    except KeyboardInterrupt:
        # Use stderr to avoid TUI interference
        sys.stderr.write("\nShutting down...\n")
        log_shutdown()
    except QwenTUIError as e:
        # Use stderr to avoid TUI interference  
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
    except Exception as e:
        logger = get_main_logger()
        logger.error("Unexpected error during startup", error=str(e), error_type=type(e).__name__)
        # Use stderr to avoid TUI interference
        sys.stderr.write(f"Unexpected error: {e}\n")
        sys.exit(1)


@backends_app.command("list")
def list_backends():
    """List all available backends and their status."""
    try:
        config = get_config()
        
        # Import here to avoid circular imports
        from ..backends.manager import BackendManager
        
        async def _run_backends_list(backend_manager):
            # Get backend status without re-initializing
            results = {}
            
            # Check all backend types
            from ..config import BackendType
            for backend_type in BackendType:
                if backend_type in backend_manager.backends:
                    # Backend is already initialized
                    backend = backend_manager.backends[backend_type]
                    try:
                        backend_info = await backend.get_info()
                        results[backend_type] = {
                            "available": True,
                            "host": backend_info.host,
                            "port": backend_info.port,
                            "model": backend_info.model,
                            "notes": "Ready to use"
                        }
                    except Exception as e:
                        results[backend_type] = {
                            "available": False,
                            "error": str(e)
                        }
                else:
                    # Backend not initialized - likely unavailable
                    results[backend_type] = {
                        "available": False,
                        "error": "Backend not available"
                    }
            
            return results
        
        with console.status("[bold blue]Checking backends..."):
            results = asyncio.run(_run_with_cleanup(config, _run_backends_list))
        
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
        
        async def _run_backends_test(backend_manager):
            return await backend_manager.test_all_backends()
        
        results = asyncio.run(_run_with_cleanup(config, _run_backends_test))
        
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


# Model Management Commands

async def _get_initialized_backend_manager(config):
    """Get an initialized backend manager."""
    from ..backends.manager import BackendManager
    backend_manager = BackendManager(config)
    await backend_manager.initialize()
    return backend_manager

async def _run_with_cleanup(config, func, *args, **kwargs):
    """Run an async function with proper backend cleanup."""
    backend_manager = await _get_initialized_backend_manager(config)
    try:
        return await func(backend_manager, *args, **kwargs)
    finally:
        await backend_manager.cleanup()

@models_app.command("list")
def list_models(
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Filter by specific backend"),
    current: bool = typer.Option(False, "--current", "-c", help="Show currently active models only"),
    recommended: bool = typer.Option(False, "--recommended", "-r", help="Show recommended coding models only")
):
    """List all available models from backends."""
    try:
        config = get_config()
        from ..backends.manager import BackendManager
        
        async def _run_list(backend_manager):
            if recommended:
                models_data = await backend_manager.get_recommended_models()
                _display_recommended_models(models_data)
            elif current:
                current_models = await backend_manager.get_current_models()
                _display_current_models(current_models)
            elif backend:
                try:
                    backend_type = BackendType(backend.lower())
                    models_data = await backend_manager.get_models_by_backend(backend_type)
                    _display_models_table({backend: models_data}, f"{backend.title()} Models")
                except ValueError:
                    available = [b.value for b in BackendType]
                    console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
                    raise typer.Exit(1)
            else:
                all_models = await backend_manager.get_all_models()
                _display_models_table(all_models, "All Available Models")
        
        with console.status("[bold blue]Loading models..."):
            asyncio.run(_run_with_cleanup(config, _run_list))
                
    except Exception as e:
        console.print(f"[red]Error listing models: {e}[/red]")
        sys.exit(1)


@models_app.command("switch")
def switch_model(
    backend: str = typer.Argument(..., help="Backend to switch model on"),
    model: str = typer.Argument(..., help="Model ID to switch to"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify model availability before switching")
):
    """Switch to a specific model on a backend."""
    try:
        config = get_config()
        
        try:
            backend_type = BackendType(backend.lower())
        except ValueError:
            available = [b.value for b in BackendType]
            console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
            raise typer.Exit(1)
            
        async def _switch_model(backend_manager):
            # Verify model availability if requested
            if verify:
                is_available = await backend_manager.is_model_available(backend_type, model)
                
                if not is_available:
                    console.print(f"[red]Model '{model}' is not available on {backend}[/red]")
                    
                    # Show available models
                    models = await backend_manager.get_models_by_backend(backend_type)
                    if models:
                        console.print(f"\n[yellow]Available models on {backend}:[/yellow]")
                        for m in models[:10]:  # Show first 10
                            console.print(f"  • {m['id']}")
                        if len(models) > 10:
                            console.print(f"  ... and {len(models) - 10} more")
                    
                    return False
            
            # Attempt to switch model
            success = await backend_manager.switch_model(backend_type, model)
            
            if success:
                console.print(f"[green]✓[/green] Successfully switched {backend} to model: {model}")
                
                # Show model info if available
                model_info = await backend_manager.get_model_info(backend_type, model)
                if model_info and 'details' in model_info:
                    details = model_info['details']
                    console.print(f"  [dim]Created: {details.get('created', 'Unknown')}[/dim]")
                    console.print(f"  [dim]Owner: {details.get('owned_by', 'Unknown')}[/dim]")
                return True
            else:
                console.print(f"[red]✗[/red] Failed to switch {backend} to model: {model}")
                
                if backend == "lm_studio":
                    console.print("[yellow]Note: LM Studio requires manual model switching through the GUI[/yellow]")
                
                return False
        
        # Run with proper initialization and cleanup
        with console.status(f"[bold blue]Switching {backend} to {model}..."):
            success = asyncio.run(_run_with_cleanup(config, _switch_model))
            
            if not success:
                sys.exit(1)
                
    except Exception as e:
        console.print(f"[red]Error switching model: {e}[/red]")
        sys.exit(1)


@models_app.command("info")
def model_info(
    backend: str = typer.Argument(..., help="Backend name"),
    model: str = typer.Argument(..., help="Model ID to get info for")
):
    """Get detailed information about a specific model."""
    try:
        config = get_config()
        from ..backends.manager import BackendManager
        
        backend_manager = BackendManager(config)
        
        try:
            backend_type = BackendType(backend.lower())
        except ValueError:
            available = [b.value for b in BackendType]
            console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
            raise typer.Exit(1)
        
        with console.status(f"[bold blue]Getting info for {model}..."):
            model_info = asyncio.run(backend_manager.get_model_info(backend_type, model))
            
            if not model_info:
                console.print(f"[red]Model '{model}' not found on {backend}[/red]")
                sys.exit(1)
            
            # Display model information
            console.print(Panel.fit(
                f"[bold cyan]{model_info['id']}[/bold cyan]\n\n" +
                f"[bold]Backend:[/bold] {model_info['backend']}\n" +
                f"[bold]Type:[/bold] {model_info.get('object', 'model')}\n" +
                f"[bold]Owner:[/bold] {model_info.get('owned_by', 'local')}\n" +
                (f"[bold]Created:[/bold] {model_info.get('created', 'Unknown')}\n" if model_info.get('created') else ""),
                title="Model Information"
            ))
            
            # Show additional details if available
            if 'details' in model_info:
                details = model_info['details']
                if isinstance(details, dict) and len(details) > 4:  # More than basic fields
                    console.print("\n[bold]Additional Details:[/bold]")
                    for key, value in details.items():
                        if key not in ['id', 'object', 'owned_by', 'created']:
                            console.print(f"  [dim]{key}:[/dim] {value}")
                            
    except Exception as e:
        console.print(f"[red]Error getting model info: {e}[/red]")
        sys.exit(1)


@models_app.command("search")
def search_models(
    pattern: str = typer.Argument(..., help="Search pattern to match against model names"),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", "-s", help="Case sensitive search")
):
    """Search for models across all backends."""
    try:
        config = get_config()
        
        async def _search_models(backend_manager):
            if case_sensitive:
                # Override the find function for case-sensitive search
                all_models = await backend_manager.get_all_models()
                matching_models = []
                for backend, models in all_models.items():
                    for model in models:
                        if pattern in model['id'] or pattern in model['name']:
                            matching_models.append(model)
            else:
                matching_models = await backend_manager.find_model_across_backends(pattern)
            
            if not matching_models:
                console.print(f"[yellow]No models found matching '{pattern}'[/yellow]")
                return
            
            # Group by backend for display
            grouped_models = {}
            for model in matching_models:
                backend = model['backend']
                if backend not in grouped_models:
                    grouped_models[backend] = []
                grouped_models[backend].append(model)
            
            _display_models_table(grouped_models, f"Models matching '{pattern}'")
        
        with console.status(f"[bold blue]Searching for models matching '{pattern}'..."):
            asyncio.run(_run_with_cleanup(config, _search_models))
            
    except Exception as e:
        console.print(f"[red]Error searching models: {e}[/red]")
        sys.exit(1)


@models_app.command("current")
def show_current_models():
    """Show currently active/loaded models for each backend."""
    try:
        config = get_config()
        
        async def _run_current(backend_manager):
            current_models = await backend_manager.get_current_models()
            _display_current_models(current_models)
        
        with console.status("[bold blue]Getting current models..."):
            asyncio.run(_run_with_cleanup(config, _run_current))
            
    except Exception as e:
        console.print(f"[red]Error getting current models: {e}[/red]")
        sys.exit(1)


@models_app.command("set-default")
def set_default_model(
    backend: str = typer.Argument(..., help="Backend to set default model for"),
    model: str = typer.Argument(..., help="Model ID to set as default"),
    save_to_config: bool = typer.Option(True, "--save/--no-save", help="Save to configuration file")
):
    """Set the default model for a backend."""
    try:
        config = get_config()
        
        try:
            backend_type = BackendType(backend.lower())
        except ValueError:
            available = [b.value for b in BackendType]
            console.print(f"[red]Invalid backend '{backend}'. Available: {', '.join(available)}[/red]")
            raise typer.Exit(1)
        
        # Verify model exists if backend is available
        from ..backends.manager import BackendManager
        backend_manager = BackendManager(config)
        
        try:
            is_available = asyncio.run(backend_manager.is_model_available(backend_type, model))
            if not is_available:
                console.print(f"[yellow]Warning: Model '{model}' is not currently available on {backend}[/yellow]")
                if not typer.confirm("Set as default anyway?"):
                    raise typer.Exit(0)
        except Exception:
            console.print(f"[yellow]Warning: Could not verify model availability on {backend}[/yellow]")
        
        # Update configuration
        if backend_type == BackendType.OLLAMA:
            config.ollama.model = model
        elif backend_type == BackendType.LM_STUDIO:
            config.lm_studio.api_key = config.lm_studio.api_key  # Keep existing settings
        elif backend_type == BackendType.VLLM:
            config.vllm.model = model
        elif backend_type == BackendType.OPENROUTER:
            config.openrouter.model = model
        
        console.print(f"[green]✓[/green] Set default model for {backend} to: {model}")
        
        if save_to_config:
            try:
                save_config(config)
                console.print(f"[green]✓[/green] Configuration saved")
            except Exception as e:
                console.print(f"[red]Failed to save configuration: {e}[/red]")
                sys.exit(1)
                
    except Exception as e:
        console.print(f"[red]Error setting default model: {e}[/red]")
        sys.exit(1)


def _display_models_table(models_data: Union[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]], title: str):
    """Display models in a formatted table."""
    table = Table(title=title)
    table.add_column("Backend", style="cyan", no_wrap=True, width=12)
    table.add_column("Model ID", style="green", width=45, overflow="ellipsis")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Owner", style="dim", width=15, overflow="ellipsis")
    table.add_column("Status", style="bold", width=10)
    
    if isinstance(models_data, list):
        # Single backend list
        for model in models_data:
            table.add_row(
                model['backend'].title(),
                model['id'],
                model.get('object', 'model'),
                model.get('owned_by', 'local'),
                "[green]Available[/green]"
            )
    else:
        # Multiple backends
        for backend, models in models_data.items():
            if not models:
                table.add_row(
                    backend.title(),
                    "[dim]No models[/dim]",
                    "[dim]N/A[/dim]",
                    "[dim]N/A[/dim]",
                    "[red]None available[/red]"
                )
            else:
                for i, model in enumerate(models):
                    backend_name = backend.title() if i == 0 else ""
                    table.add_row(
                        backend_name,
                        model['id'],
                        model.get('object', 'model'),
                        model.get('owned_by', 'local'),
                        "[green]Available[/green]"
                    )
    
    console.print(table)


def _display_current_models(current_models: Dict[str, Optional[str]]):
    """Display currently active models."""
    table = Table(title="Currently Active Models")
    table.add_column("Backend", style="cyan", no_wrap=True)
    table.add_column("Current Model", style="green")
    table.add_column("Status", style="bold")
    
    for backend, model in current_models.items():
        if model:
            table.add_row(
                backend.title(),
                model,
                "[green]✓ Active[/green]"
            )
        else:
            table.add_row(
                backend.title(),
                "[dim]None loaded[/dim]",
                "[yellow]⚠ No model[/yellow]"
            )
    
    console.print(table)


def _display_recommended_models(models: List[Dict[str, Any]]):
    """Display recommended coding models."""
    if not models:
        console.print("[yellow]No recommended coding models found[/yellow]")
        return
    
    table = Table(title="Recommended Coding Models")
    table.add_column("Model", style="green")
    table.add_column("Backend", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Status", style="bold")
    
    for model in models:
        table.add_row(
            model['id'],
            model['backend'].title(),
            model.get('object', 'model'),
            "[green]Available[/green]"
        )
    
    console.print(table)
    console.print(f"\n[dim]Found {len(models)} recommended coding models[/dim]")


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