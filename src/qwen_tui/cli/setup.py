"""
Backend setup and configuration utilities.

Provides guided setup for different LLM backends with automatic detection
and configuration validation.
"""
import asyncio
import subprocess
import sys
from typing import Dict, Any, Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import BackendType, get_config, save_config
from ..exceptions import BackendError, ConfigurationError

console = Console()


def check_ollama_installation() -> Dict[str, Any]:
    """Check if Ollama is installed and running."""
    result = {"installed": False, "running": False, "models": []}
    
    try:
        # Check if ollama command exists
        subprocess.run(["ollama", "--version"], capture_output=True, check=True)
        result["installed"] = True
        
        # Check if ollama service is running
        try:
            subprocess.run(["ollama", "list"], capture_output=True, check=True, timeout=5)
            result["running"] = True
            
            # Get available models
            output = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if output.returncode == 0:
                lines = output.stdout.strip().split('\n')[1:]  # Skip header
                result["models"] = [line.split()[0] for line in lines if line.strip()]
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            result["running"] = False
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        result["installed"] = False
    
    return result


def check_lm_studio_running() -> Dict[str, Any]:
    """Check if LM Studio is running and accessible."""
    result = {"running": False, "port": None, "models": []}
    
    try:
        import aiohttp
        
        async def check_lms():
            ports_to_check = [1234, 1235, 8080]  # Common LM Studio ports
            
            async with aiohttp.ClientSession() as session:
                for port in ports_to_check:
                    try:
                        async with session.get(f"http://localhost:{port}/v1/models", timeout=5) as response:
                            if response.status == 200:
                                data = await response.json()
                                result["running"] = True
                                result["port"] = port
                                result["models"] = [model["id"] for model in data.get("data", [])]
                                return result
                    except:
                        continue
            
            return result
        
        return asyncio.run(check_lms())
        
    except ImportError:
        console.print("[yellow]Warning: aiohttp not available for LM Studio check[/yellow]")
        return result


def suggest_qwen_models() -> list:
    """Suggest appropriate Qwen models for coding tasks."""
    return [
        "qwen2.5-coder:latest",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        "qwen2.5:latest",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen2.5:32b"
    ]


def interactive_backend_setup(backend_type: BackendType) -> None:
    """Run interactive setup for a specific backend."""
    config = get_config()
    
    console.print(f"\n[bold blue]Setting up {backend_type.value.title()} Backend[/bold blue]\n")
    
    if backend_type == BackendType.OLLAMA:
        setup_ollama_interactive(config)
    elif backend_type == BackendType.LM_STUDIO:
        setup_lm_studio_interactive(config)
    elif backend_type == BackendType.VLLM:
        setup_vllm_interactive(config)
    elif backend_type == BackendType.OPENROUTER:
        setup_openrouter_interactive(config)
    
    # Save updated configuration
    save_config(config)


def setup_ollama_interactive(config) -> None:
    """Interactive Ollama setup."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking Ollama installation...", total=None)
        ollama_status = check_ollama_installation()
    
    if not ollama_status["installed"]:
        console.print(Panel(
            "[red]Ollama is not installed![/red]\n\n" +
            "Please install Ollama from: https://ollama.com\n" +
            "Then run: [bold]curl -fsSL https://ollama.com/install.sh | sh[/bold]",
            title="Installation Required"
        ))
        return
    
    console.print("[green]✓[/green] Ollama is installed")
    
    if not ollama_status["running"]:
        console.print("[yellow]⚠[/yellow] Ollama service is not running")
        if Confirm.ask("Would you like to start Ollama?"):
            try:
                subprocess.run(["ollama", "serve"], check=False, 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                console.print("[green]✓[/green] Ollama service started")
            except Exception as e:
                console.print(f"[red]Failed to start Ollama: {e}[/red]")
                return
    else:
        console.print("[green]✓[/green] Ollama service is running")
    
    # Configure host and port
    current_host = config.ollama.host
    current_port = config.ollama.port
    
    host = Prompt.ask("Ollama host", default=current_host)
    port = int(Prompt.ask("Ollama port", default=str(current_port)))
    
    # Model selection
    console.print("\n[bold]Available models:[/bold]")
    available_models = ollama_status.get("models", [])
    suggested_models = suggest_qwen_models()
    
    if available_models:
        console.print("Installed models:")
        for i, model in enumerate(available_models, 1):
            console.print(f"  {i}. {model}")
    
    console.print("\nSuggested Qwen coding models:")
    for model in suggested_models:
        status = "✓ Installed" if model in available_models else "Not installed"
        console.print(f"  • {model} ({status})")
    
    current_model = config.ollama.model
    model = Prompt.ask("Model to use", default=current_model)
    
    # Install model if not available
    if model not in available_models:
        if Confirm.ask(f"Model '{model}' is not installed. Install it now?"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Installing {model}...", total=None)
                try:
                    subprocess.run(["ollama", "pull", model], check=True)
                    console.print(f"[green]✓[/green] Model {model} installed successfully")
                except subprocess.CalledProcessError as e:
                    console.print(f"[red]Failed to install model: {e}[/red]")
                    return
    
    # Update configuration
    config.ollama.host = host
    config.ollama.port = port
    config.ollama.model = model
    
    console.print(f"[green]✓[/green] Ollama configuration updated")


def setup_lm_studio_interactive(config) -> None:
    """Interactive LM Studio setup."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking LM Studio...", total=None)
        lms_status = check_lm_studio_running()
    
    if not lms_status["running"]:
        console.print(Panel(
            "[yellow]LM Studio is not running or not accessible![/yellow]\n\n" +
            "Please:\n" +
            "1. Start LM Studio\n" +
            "2. Load a model\n" +
            "3. Start the local server\n" +
            "4. Ensure the server is running on localhost",
            title="LM Studio Setup Required"
        ))
        
        if not Confirm.ask("Is LM Studio running now?"):
            return
        
        # Re-check after user confirmation
        lms_status = check_lm_studio_running()
        if not lms_status["running"]:
            console.print("[red]Still cannot connect to LM Studio[/red]")
            return
    
    console.print(f"[green]✓[/green] LM Studio is running on port {lms_status['port']}")
    
    # Configure connection
    current_host = config.lm_studio.host
    current_port = config.lm_studio.port
    
    host = Prompt.ask("LM Studio host", default=current_host)
    port = int(Prompt.ask("LM Studio port", default=str(lms_status.get("port", current_port))))
    
    # Show available models
    if lms_status["models"]:
        console.print("\n[bold]Available models in LM Studio:[/bold]")
        for model in lms_status["models"]:
            console.print(f"  • {model}")
    
    # Update configuration
    config.lm_studio.host = host
    config.lm_studio.port = port
    
    console.print("[green]✓[/green] LM Studio configuration updated")


def setup_vllm_interactive(config) -> None:
    """Interactive vLLM setup."""
    console.print(Panel(
        "[blue]vLLM Setup[/blue]\n\n" +
        "vLLM requires manual installation and setup.\n" +
        "Please refer to: https://docs.vllm.ai/en/latest/getting_started/installation.html\n\n" +
        "After installation, start vLLM with:\n" +
        "[bold]python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-Coder-7B-Instruct[/bold]",
        title="vLLM Configuration"
    ))
    
    # Configure connection details
    current_host = config.vllm.host
    current_port = config.vllm.port
    current_model = config.vllm.model
    
    host = Prompt.ask("vLLM host", default=current_host)
    port = int(Prompt.ask("vLLM port", default=str(current_port)))
    model = Prompt.ask("Model path/name", default=current_model)
    
    # Advanced settings
    if Confirm.ask("Configure advanced settings?", default=False):
        max_tokens = int(Prompt.ask("Max tokens", default=str(config.vllm.max_tokens)))
        temperature = float(Prompt.ask("Temperature", default=str(config.vllm.temperature)))
        
        config.vllm.max_tokens = max_tokens
        config.vllm.temperature = temperature
    
    # Update configuration
    config.vllm.host = host
    config.vllm.port = port
    config.vllm.model = model
    
    console.print("[green]✓[/green] vLLM configuration updated")


def setup_openrouter_interactive(config) -> None:
    """Interactive OpenRouter setup."""
    console.print(Panel(
        "[blue]OpenRouter Setup[/blue]\n\n" +
        "OpenRouter provides access to various LLMs including Qwen models.\n" +
        "You'll need an API key from: https://openrouter.ai/keys",
        title="OpenRouter Configuration"
    ))
    
    # API Key
    current_key = config.openrouter.api_key
    if current_key and current_key != "":
        key_display = f"{current_key[:8]}..." if len(current_key) > 8 else current_key
        api_key = Prompt.ask("OpenRouter API key", default=key_display, password=True)
        if api_key == key_display:
            api_key = current_key  # Keep existing key
    else:
        api_key = Prompt.ask("OpenRouter API key", password=True)
    
    if not api_key:
        console.print("[red]API key is required for OpenRouter[/red]")
        return
    
    # Model selection
    suggested_models = [
        "qwen/qwen-2.5-coder-32b-instruct",
        "qwen/qwen-2.5-coder-14b-instruct",
        "qwen/qwen-2.5-coder-7b-instruct",
        "qwen/qwen-2.5-32b-instruct",
        "qwen/qwen-2.5-14b-instruct",
        "qwen/qwen-2.5-7b-instruct"
    ]
    
    console.print("\n[bold]Suggested Qwen models on OpenRouter:[/bold]")
    for i, model in enumerate(suggested_models, 1):
        console.print(f"  {i}. {model}")
    
    current_model = config.openrouter.model
    model = Prompt.ask("Model to use", default=current_model)
    
    # Update configuration
    config.openrouter.api_key = api_key
    config.openrouter.model = model
    
    console.print("[green]✓[/green] OpenRouter configuration updated")


def automated_backend_setup(backend_type: BackendType) -> None:
    """Run automated setup for a specific backend (non-interactive)."""
    console.print(f"[yellow]Automated setup for {backend_type.value} is not yet implemented[/yellow]")
    console.print("Please use interactive setup: --interactive")


def detect_available_backends() -> Dict[BackendType, Dict[str, Any]]:
    """Detect all available backends and their status."""
    results = {}
    
    # Check Ollama
    ollama_status = check_ollama_installation()
    results[BackendType.OLLAMA] = {
        "available": ollama_status["installed"] and ollama_status["running"],
        "details": ollama_status
    }
    
    # Check LM Studio
    lms_status = check_lm_studio_running()
    results[BackendType.LM_STUDIO] = {
        "available": lms_status["running"],
        "details": lms_status
    }
    
    # vLLM and OpenRouter require configuration, so mark as available if configured
    config = get_config()
    
    results[BackendType.VLLM] = {
        "available": False,  # Would need actual connectivity test
        "details": {"configured": bool(config.vllm.host)}
    }
    
    results[BackendType.OPENROUTER] = {
        "available": bool(config.openrouter.api_key),
        "details": {"configured": bool(config.openrouter.api_key)}
    }
    
    return results