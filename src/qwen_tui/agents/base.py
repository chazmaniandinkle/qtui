"""
Base agent system with Claude Code-quality prompts and behavior.

This module provides the foundational agent class with sophisticated
prompting, tool usage, and reasoning capabilities.
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from ..backends.base import LLMRequest, LLMResponse
from ..backends.manager import BackendManager
from ..tools import ToolManager, ToolResult, ToolStatus
from ..logging import get_main_logger


class AgentMode(Enum):
    """Different modes of agent operation."""
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"
    PLANNING = "planning"
    EXECUTION = "execution"


class ReasoningPhase(Enum):
    """Phases of agent reasoning."""
    ANALYSIS = "analysis"
    PLANNING = "planning"
    TOOL_SELECTION = "tool_selection"
    EXECUTION = "execution"
    SYNTHESIS = "synthesis"
    REFLECTION = "reflection"


@dataclass
class AgentState:
    """Current state of the agent."""
    mode: AgentMode
    phase: ReasoningPhase
    context: Dict[str, Any]
    working_directory: Optional[str] = None
    session_id: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents with Claude Code-style capabilities."""
    
    SYSTEM_PROMPT = """You are an advanced AI coding assistant with access to a comprehensive set of tools for file manipulation, code analysis, and system interaction. Your capabilities closely mirror those of Claude Code.

# Core Principles

1. **Precision and Accuracy**: Always read files before editing them. Understand the codebase context before making changes.

2. **Methodical Approach**: Break complex tasks into clear, logical steps. Use your thinking process to plan before acting.

3. **Tool Mastery**: You have access to powerful tools - use them effectively:
   - Read, Write, Edit, MultiEdit for file operations
   - Grep, Glob, LS for code exploration  
   - Bash for system commands
   - Task for delegating complex work

4. **Context Awareness**: Maintain awareness of:
   - File relationships and dependencies
   - Code conventions and patterns
   - Project structure and architecture
   - User intent and requirements

5. **Error Handling**: Anticipate potential issues and handle errors gracefully.

# Tool Usage Guidelines

- **Always read files before editing** to understand current content
- **Use Grep and Glob for exploration** when searching for code patterns
- **Batch related operations** when possible (e.g., MultiEdit for multiple changes)
- **Validate your changes** by reading the modified files
- **Use Bash for testing** commands like linting, building, or running tests

# Thinking Process

Use <think> tags for your internal reasoning:
- Analyze the problem and requirements
- Plan your approach and tool usage
- Consider potential issues and edge cases
- Reflect on results and next steps

# Response Format

Provide clear, concise responses that:
- Explain what you're doing and why
- Show the results of your actions
- Identify any issues or concerns
- Suggest next steps when appropriate

Remember: You are a sophisticated coding assistant. Use your tools wisely, think carefully, and provide exceptional assistance."""

    def __init__(self, backend_manager: BackendManager, tool_manager: ToolManager, 
                 agent_id: Optional[str] = None):
        self.backend_manager = backend_manager
        self.tool_manager = tool_manager
        self.agent_id = agent_id or f"agent_{int(time.time())}"
        self.logger = get_main_logger()
        
        self.state = AgentState(
            mode=AgentMode.INTERACTIVE,
            phase=ReasoningPhase.ANALYSIS,
            context={}
        )
        
        self.conversation_history: List[Dict[str, str]] = []
        self.tool_execution_history: List[Dict[str, Any]] = []

    def set_working_directory(self, path: str) -> None:
        """Set the working directory for this agent."""
        self.state.working_directory = path
        self.tool_manager.set_working_directory(path)
        self.logger.info(f"Agent {self.agent_id} working directory set to: {path}")

    def add_context(self, key: str, value: Any) -> None:
        """Add context information for the agent."""
        self.state.context[key] = value
        self.logger.debug(f"Added context to agent {self.agent_id}: {key}")

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        base_prompt = self.SYSTEM_PROMPT
        
        # Add context-specific information
        if self.state.working_directory:
            base_prompt += f"\n\n# Working Directory\nYou are currently working in: {self.state.working_directory}"
        
        if self.state.context:
            base_prompt += "\n\n# Current Context\n"
            for key, value in self.state.context.items():
                base_prompt += f"- {key}: {value}\n"
        
        return base_prompt

    def _format_tool_schemas(self) -> str:
        """Format available tools for the prompt."""
        schemas = self.tool_manager.registry.get_tool_schemas()
        
        tool_info = "# Available Tools\n\n"
        for name, schema in schemas.items():
            tool_info += f"## {name}\n"
            tool_info += f"{schema['description']}\n\n"
            
            params = schema['parameters'].get('properties', {})
            required = schema['parameters'].get('required', [])
            
            if params:
                tool_info += "Parameters:\n"
                for param_name, param_info in params.items():
                    required_marker = " (required)" if param_name in required else ""
                    tool_info += f"- {param_name}{required_marker}: {param_info.get('description', 'No description')}\n"
            tool_info += "\n"
        
        return tool_info

    async def _execute_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a single tool call with logging."""
        self.logger.info(f"Agent {self.agent_id} executing tool: {tool_name}", parameters=parameters)
        
        result = await self.tool_manager.registry.execute_tool(tool_name, parameters)
        
        # Log to execution history
        self.tool_execution_history.append({
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result.to_dict(),
            "timestamp": time.time()
        })
        
        self.logger.info(f"Tool {tool_name} completed", status=result.status.value)
        return result

    def _extract_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """Extract tool calls from agent response."""
        # This is a simplified parser - in production would use more sophisticated parsing
        import re
        
        tool_calls = []
        
        # Look for function call patterns
        function_pattern = r'<function_call>\s*(\w+)\((.*?)\)\s*</function_call>'
        matches = re.findall(function_pattern, content, re.DOTALL)
        
        for tool_name, params_str in matches:
            try:
                # Parse parameters (simplified - would need more robust parsing)
                if params_str.strip():
                    # Try to parse as JSON-like
                    params = {}
                    for param in params_str.split(','):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            key = key.strip().strip('"\'')
                            value = value.strip().strip('"\'')
                            params[key] = value
                else:
                    params = {}
                
                tool_calls.append({
                    "name": tool_name,
                    "parameters": params
                })
            except Exception as e:
                self.logger.warning(f"Failed to parse tool call: {e}")
        
        return tool_calls

    async def _generate_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Generate response from the backend."""
        request = LLMRequest(messages=messages, stream=True)
        
        async for response in self.backend_manager.generate(request):
            if response.delta:
                yield response.delta
            elif response.content:
                yield response.content

    @abstractmethod
    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process a user message and generate response."""
        pass

    async def execute_autonomous_task(self, task: str) -> str:
        """Execute a task autonomously with full reasoning."""
        self.state.mode = AgentMode.AUTONOMOUS
        self.state.phase = ReasoningPhase.ANALYSIS
        
        # Start with analysis
        analysis_prompt = f"""
<think>
I need to analyze this task carefully:
{task}

Let me break this down:
1. What is being asked?
2. What tools will I need?
3. What's the best approach?
4. What are potential challenges?
</think>

I'll help you with: {task}

Let me start by analyzing what needs to be done.
"""
        
        full_response = ""
        async for chunk in self.process_message(analysis_prompt):
            full_response += chunk
        
        return full_response


class CodingAgent(BaseAgent):
    """Specialized agent for coding tasks."""
    
    SYSTEM_PROMPT = BaseAgent.SYSTEM_PROMPT + """

# Coding Specialization

You are specifically optimized for coding tasks. Additional guidelines:

## Code Quality
- Follow existing code style and conventions
- Write clean, readable, and maintainable code
- Add appropriate comments and documentation
- Consider performance and security implications

## Testing and Validation
- Run tests after making changes
- Validate that your changes don't break existing functionality
- Use linting tools to ensure code quality

## Best Practices
- Make incremental changes when possible
- Back up important files before major changes
- Use version control principles (atomic commits)
- Consider the impact on other parts of the codebase

## Tool Usage for Coding
- Use Read extensively to understand existing code
- Use Grep to find similar patterns and implementations
- Use MultiEdit for coordinated changes across files
- Use Bash to run tests, builds, and validation commands
"""

    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process message with coding-specific behavior."""
        # Add system prompt and tool information
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "system", "content": self._format_tool_schemas()},
            {"role": "user", "content": message}
        ]
        
        # Add conversation history
        messages.extend(self.conversation_history[-10:])  # Keep last 10 messages
        messages.append({"role": "user", "content": message})
        
        full_response = ""
        
        async for chunk in self._generate_response(messages):
            full_response += chunk
            yield chunk
        
        # Process tool calls if any
        tool_calls = self._extract_tool_calls(full_response)
        
        if tool_calls:
            yield "\n\n--- Executing Tools ---\n\n"
            
            for call in tool_calls:
                tool_name = call["name"]
                parameters = call["parameters"]
                
                yield f"🔧 Executing {tool_name}...\n"
                
                result = await self._execute_tool_call(tool_name, parameters)
                
                if result.is_success():
                    yield f"✅ {tool_name} completed successfully\n"
                    if result.result:
                        yield f"Result: {result.result}\n"
                else:
                    yield f"❌ {tool_name} failed: {result.error}\n"
                
                yield "\n"
        
        # Update conversation history
        self.conversation_history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": full_response}
        ])


class AnalysisAgent(BaseAgent):
    """Specialized agent for code analysis and exploration."""
    
    SYSTEM_PROMPT = BaseAgent.SYSTEM_PROMPT + """

# Analysis Specialization

You excel at understanding and analyzing codebases. Additional guidelines:

## Code Analysis
- Use Grep and Glob extensively to explore codebases
- Identify patterns, architectures, and design decisions
- Understand dependencies and relationships between components
- Analyze code quality, potential issues, and improvement opportunities

## Exploration Strategy
- Start with high-level structure (directories, main files)
- Dive into specific areas based on the task
- Look for configuration files, documentation, and tests
- Identify entry points and key interfaces

## Reporting
- Provide clear, structured analysis
- Highlight important findings and insights
- Suggest areas for improvement or investigation
- Create summaries and recommendations
"""

    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process message with analysis-specific behavior."""
        # Implementation similar to CodingAgent but optimized for analysis
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "system", "content": self._format_tool_schemas()},
            {"role": "user", "content": message}
        ]
        
        async for chunk in self._generate_response(messages):
            yield chunk