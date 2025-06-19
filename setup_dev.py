#!/usr/bin/env python3
"""
Development setup script for Qwen-TUI.

This script helps set up the development environment and verifies
that all basic functionality is working.
"""
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print its status."""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"   Error: {e.stderr}")
        return False

def main():
    """Main setup function."""
    print("🚀 Setting up Qwen-TUI development environment...\n")
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Please run this script from the qwen-tui root directory")
        sys.exit(1)
    
    success_count = 0
    total_checks = 6
    
    # Install in development mode
    if run_command("python -m pip install -e .[dev]", "Installing Qwen-TUI in development mode"):
        success_count += 1
    
    # Test basic CLI functionality
    if run_command("qwen-tui --help", "Testing CLI help command"):
        success_count += 1
    
    # Test version command
    if run_command("qwen-tui version", "Testing version command"):
        success_count += 1
    
    # Test backend discovery
    if run_command("qwen-tui backends list", "Testing backend discovery"):
        success_count += 1
    
    # Run configuration tests
    if run_command("python -m pytest tests/test_config.py -v", "Running configuration tests"):
        success_count += 1
    
    # Test import structure
    if run_command("python -c 'import qwen_tui; print(f\"Qwen-TUI v{qwen_tui.__version__} imported successfully\")'", "Testing Python imports"):
        success_count += 1
    
    print(f"\n🎯 Setup Summary: {success_count}/{total_checks} checks passed")
    
    if success_count == total_checks:
        print("\n🎉 Qwen-TUI development environment is ready!")
        print("\n📝 Next steps:")
        print("   1. Install Ollama: https://ollama.com")
        print("   2. Pull a Qwen model: ollama pull qwen2.5-coder:latest")
        print("   3. Start Qwen-TUI: qwen-tui start")
        print("   4. Configure other backends: qwen-tui backends setup <backend>")
        print("   5. Check out the implementation guide: docs/qwen_tui_implementation_guide.md")
    else:
        print(f"\n⚠️  {total_checks - success_count} checks failed. Please review the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()