#!/usr/bin/env python3
"""
Interactive Agent Console - Direct testing interface for the advanced agent system.

This provides a simple command-line interface to test and interact with the 
agent system directly, bypassing TUI complexity for debugging purposes.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from qwen_tui.backends.manager import BackendManager
from qwen_tui.config import Config
from qwen_tui.tui.thinking import ThinkingManager
from qwen_tui.tools import get_tool_manager
from qwen_tui.agents import get_agent_factory


class InteractiveAgentConsole:
    """Interactive console for testing the agent system."""
    
    def __init__(self):
        self.config = Config()
        self.backend_manager = None
        self.thinking_manager = None
        self.agent = None
        
    async def initialize(self):
        """Initialize all components."""
        print("🚀 Interactive Agent Console")
        print("=" * 50)
        
        # Initialize backend manager
        print("📡 Initializing backends...")
        self.backend_manager = BackendManager(self.config)
        
        try:
            await self.backend_manager.initialize()
            backends = self.backend_manager.get_available_backends()
            print(f"✅ Found {len(backends)} backend(s)")
            for backend in backends:
                print(f"   - {backend.name}")
        except Exception as e:
            print(f"❌ Backend initialization failed: {e}")
            return False
        
        # Initialize thinking manager
        print("🧠 Initializing thinking system...")
        self.thinking_manager = ThinkingManager(self.backend_manager, self.config)
        
        try:
            await self.thinking_manager.initialize()
            print("✅ Thinking system ready")
        except Exception as e:
            print(f"❌ Thinking system failed: {e}")
            return False
        
        # Create direct agent for comparison
        print("🤖 Creating ReAct agent...")
        try:
            tool_manager = get_tool_manager()
            agent_factory = get_agent_factory(self.backend_manager, tool_manager)
            self.agent = agent_factory.create_coding_agent(
                working_directory=str(Path.cwd()),
                language="python"
            )
            print("✅ ReAct agent ready")
        except Exception as e:
            print(f"❌ Agent creation failed: {e}")
            return False
        
        return True
    
    async def run_interactive_session(self):
        """Run the interactive testing session."""
        print("\n💬 Interactive Agent Testing Session")
        print("=" * 50)
        print("Commands:")
        print("  'quit' or 'exit' - Exit the console")
        print("  'tools' - Test individual tools")
        print("  'agent' - Test direct agent interaction")
        print("  'thinking' - Test thinking system")
        print("  'help' - Show this help")
        print("  Any other input - Send to thinking system")
        print()
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                elif user_input.lower() == 'help':
                    self._show_help()
                
                elif user_input.lower() == 'tools':
                    await self._test_tools()
                
                elif user_input.lower() == 'agent':
                    await self._test_direct_agent()
                
                elif user_input.lower() == 'thinking':
                    await self._test_thinking_system()
                
                elif not user_input:
                    continue
                
                else:
                    # Send to thinking system
                    print("🧠 Thinking System Response:")
                    try:
                        async for chunk in self.thinking_manager.think_and_respond(user_input):
                            print(chunk, end="", flush=True)
                        print()  # New line after response
                    except Exception as e:
                        print(f"❌ Error: {e}")
                
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        
        print("\n👋 Session ended!")
    
    def _show_help(self):
        """Show help information."""
        print("""
🔧 Available Commands:

Direct Testing:
  tools     - Test individual tools (Read, Write, Bash, etc.)
  agent     - Test ReAct agent directly  
  thinking  - Test full thinking system

System Info:
  help      - Show this help message
  quit/exit - Exit the console

Message Processing:
  Any other input will be sent to the thinking system for processing.

Example interactions:
  "Read the README file"
  "List files in the current directory"
  "Create a simple Python script"
  "Search for TODO comments in the code"
""")
    
    async def _test_tools(self):
        """Test individual tools."""
        print("\n🔧 Tool Testing Mode")
        print("-" * 30)
        
        tool_manager = get_tool_manager()
        available_tools = tool_manager.registry.list_tools()
        
        print("Available tools:")
        for i, tool_name in enumerate(available_tools, 1):
            print(f"  {i}. {tool_name}")
        
        try:
            choice = input("\nEnter tool number to test (or 'back'): ").strip()
            if choice.lower() == 'back':
                return
            
            tool_index = int(choice) - 1
            if 0 <= tool_index < len(available_tools):
                tool_name = available_tools[tool_index]
                await self._test_specific_tool(tool_name)
            else:
                print("❌ Invalid tool number")
                
        except ValueError:
            print("❌ Please enter a valid number")
    
    async def _test_specific_tool(self, tool_name: str):
        """Test a specific tool with sample parameters."""
        tool_manager = get_tool_manager()
        tool = tool_manager.registry.get_tool(tool_name)
        
        if not tool:
            print(f"❌ Tool {tool_name} not found")
            return
        
        print(f"\n🧪 Testing {tool_name}")
        print(f"Description: {tool.description}")
        
        # Provide sample parameters based on tool type
        test_params = {
            "Read": {"file_path": __file__, "limit": 5},
            "Write": {"file_path": "test_console_output.txt", "content": "Hello from console test!"},
            "LS": {"path": "."},
            "Bash": {"command": "echo 'Tool test successful'", "description": "Test echo command"},
            "Grep": {"pattern": "def", "include": "*.py"},
            "Glob": {"pattern": "*.py"},
        }
        
        params = test_params.get(tool_name, {})
        
        if not params:
            print("⚠️  No test parameters defined for this tool")
            return
        
        print(f"Parameters: {params}")
        
        try:
            result = await tool.safe_execute(**params)
            print(f"Status: {result.status.value}")
            
            if result.is_success():
                output = str(result.result)
                if len(output) > 300:
                    print(f"Result: {output[:300]}...")
                else:
                    print(f"Result: {output}")
            else:
                print(f"Error: {result.error}")
                
        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
    
    async def _test_direct_agent(self):
        """Test direct agent interaction."""
        print("\n🤖 Direct Agent Testing")
        print("-" * 30)
        
        if not self.agent:
            print("❌ Agent not available")
            return
        
        message = input("Enter message for agent: ").strip()
        if not message:
            return
        
        print("🤖 Agent Response:")
        try:
            async for chunk in self.agent.process_message(message):
                print(chunk, end="", flush=True)
            print()  # New line
        except Exception as e:
            print(f"❌ Agent error: {e}")
    
    async def _test_thinking_system(self):
        """Test the thinking system specifically."""
        print("\n🧠 Thinking System Test")
        print("-" * 30)
        
        test_queries = [
            "Hello! Can you read this file and tell me what it does?",
            "List all Python files in the current directory",
            "Create a simple test file"
        ]
        
        print("Select a test query:")
        for i, query in enumerate(test_queries, 1):
            print(f"  {i}. {query}")
        print("  4. Custom query")
        
        try:
            choice = input("\nChoice (1-4): ").strip()
            
            if choice == "4":
                query = input("Enter custom query: ").strip()
            elif choice in ["1", "2", "3"]:
                query = test_queries[int(choice) - 1]
            else:
                print("❌ Invalid choice")
                return
            
            if not query:
                return
            
            print(f"\n🧠 Processing: {query}")
            print("Response:")
            
            async for chunk in self.thinking_manager.think_and_respond(query):
                print(chunk, end="", flush=True)
            print()  # New line
            
        except ValueError:
            print("❌ Please enter a valid number")
        except Exception as e:
            print(f"❌ Thinking system error: {e}")


async def main():
    """Main entry point."""
    console = InteractiveAgentConsole()
    
    if await console.initialize():
        await console.run_interactive_session()
    else:
        print("❌ Failed to initialize console")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Console interrupted")
        sys.exit(0)