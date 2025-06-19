"""
ReAct (Reason and Act) agent implementation following Claude Code's pattern.

This module implements the Plan → Act → Observe loop with sophisticated
reasoning and tool execution capabilities.
"""
import asyncio
import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentMode, ReasoningPhase
from ..tools import ToolManager, ToolResult, ToolStatus
from ..backends.manager import BackendManager
from ..logging import get_main_logger


class ActionType(Enum):
    """Types of actions the agent can take."""
    THINK = "think"
    TOOL_USE = "tool_use"
    RESPOND = "respond"
    PLAN = "plan"
    OBSERVE = "observe"


@dataclass
class AgentAction:
    """Represents an action taken by the agent."""
    action_type: ActionType
    content: str
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ReActAgent(BaseAgent):
    """ReAct agent implementing Plan-Act-Observe loop."""
    
    SYSTEM_PROMPT = """You are Claude Code, an advanced AI coding assistant that follows the ReAct paradigm (Reason and Act). You have access to a comprehensive set of tools for file manipulation, code analysis, and system interaction.

# Core Principles

1. **Plan-Act-Observe Loop**: Break down complex tasks into clear steps:
   - **Plan**: Analyze the problem and create a strategy
   - **Act**: Execute specific actions using your tools
   - **Observe**: Examine results and plan next steps

2. **Systematic Reasoning**: Use <think> tags for internal reasoning:
   - Analyze the current situation
   - Consider available options and tools
   - Plan the next logical step
   - Reflect on results and adjust strategy

3. **Tool Mastery**: You have access to powerful tools - use them effectively:
   - **File Operations**: Read, Write, Edit, MultiEdit for precise file manipulation
   - **Code Analysis**: Grep, Glob, LS for codebase exploration
   - **Execution**: Bash for running commands and scripts
   - **Delegation**: Task for complex sub-operations

4. **Contextual Awareness**: Always understand:
   - Current working directory and file structure
   - Existing code patterns and conventions
   - Project architecture and dependencies
   - User goals and requirements

# Tool Usage Strategy

## File Operations
- **Always read files before editing** to understand current content
- Use **Edit** for single changes, **MultiEdit** for coordinated changes
- Validate changes by reading modified files

## Code Exploration
- Use **Grep** to find code patterns and implementations
- Use **Glob** to locate files by name patterns
- Use **LS** to understand directory structure

## Command Execution
- Use **Bash** for testing, building, and validation
- Always explain what commands do before running them
- Capture and analyze command output

## Task Delegation
- Use **Task** for complex sub-operations that need focused attention
- Provide clear, specific instructions for sub-tasks

# Response Format

Structure your responses with clear phases:

1. **Analysis** (in <think> tags): Break down the problem
2. **Planning**: Outline your approach 
3. **Execution**: Take concrete actions with tools
4. **Observation**: Analyze results and plan next steps
5. **Summary**: Provide clear status and recommendations

# Visual Indicators

Use these indicators for clarity:
- 🎯 **Planning phase**
- ⏺ **Tool execution in progress** 
- ⎿ **Tool completion**
- 🤔 **Thinking/reasoning**
- ✅ **Success**
- ❌ **Error/failure**
- ⚠️ **Warning/caution**

# Error Handling

When errors occur:
1. Analyze the error message carefully
2. Consider alternative approaches
3. Provide helpful explanations to the user
4. Suggest corrective actions when possible

Remember: You are a sophisticated coding assistant. Think systematically, use tools effectively, and provide exceptional assistance through the Plan-Act-Observe methodology."""

    def __init__(self, backend_manager: BackendManager, tool_manager: ToolManager,
                 agent_id: Optional[str] = None):
        super().__init__(backend_manager, tool_manager, agent_id)
        self.action_history: List[AgentAction] = []
        self.current_plan: List[str] = []
        self.context_snapshot: Dict[str, Any] = {}

    def _extract_thinking_content(self, text: str) -> Tuple[str, str]:
        """Extract thinking content from <think> tags."""
        think_pattern = r'<think>(.*?)</think>'
        think_matches = re.findall(think_pattern, text, re.DOTALL | re.IGNORECASE)
        thinking_content = '\n'.join(think_matches) if think_matches else ''
        
        # Remove thinking tags from visible content
        visible_content = re.sub(think_pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
        return visible_content.strip(), thinking_content.strip()

    def _extract_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """Extract tool calls from agent response using multiple patterns."""
        tool_calls = []
        
        # Pattern 1: Explicit function calls
        function_pattern = r'<function_call>\s*(\w+)\((.*?)\)\s*</function_call>'
        matches = re.findall(function_pattern, content, re.DOTALL)
        
        for tool_name, params_str in matches:
            try:
                params = self._parse_parameters(params_str)
                tool_calls.append({
                    "name": tool_name,
                    "parameters": params
                })
            except Exception as e:
                self.logger.warning(f"Failed to parse function call: {e}")
        
        # Pattern 2: Tool invocation format
        tool_pattern = r'(\w+)\s*\(\s*(.*?)\s*\)'
        
        # Look for common tool names
        tool_names = self.tool_manager.registry.list_tools()
        for tool_name in tool_names:
            pattern = rf'\b{tool_name}\s*\(\s*(.*?)\s*\)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for params_str in matches:
                try:
                    params = self._parse_parameters(params_str)
                    tool_calls.append({
                        "name": tool_name,
                        "parameters": params
                    })
                except Exception as e:
                    self.logger.warning(f"Failed to parse tool call {tool_name}: {e}")
        
        return tool_calls

    def _parse_parameters(self, params_str: str) -> Dict[str, Any]:
        """Parse tool parameters from string."""
        params = {}
        
        if not params_str.strip():
            return params
        
        try:
            # Try JSON parsing first
            if params_str.strip().startswith('{'):
                return json.loads(params_str)
        except json.JSONDecodeError:
            pass
        
        # Parse key=value pairs
        for param in params_str.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().strip('"\'')
                value = value.strip().strip('"\'')
                
                # Try to convert to appropriate type
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
                
                params[key] = value
        
        return params

    async def _create_context_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the current context."""
        snapshot = {
            "timestamp": time.time(),
            "working_directory": self.state.working_directory,
            "conversation_length": len(self.conversation_history)
        }
        
        # Add directory structure if working directory is set
        if self.state.working_directory:
            try:
                ls_tool = self.tool_manager.registry.get_tool("LS")
                if ls_tool:
                    result = await ls_tool.safe_execute(
                        path=self.state.working_directory,
                        recursive=True,
                        max_depth=2
                    )
                    if result.is_success():
                        snapshot["directory_structure"] = result.result
            except Exception as e:
                self.logger.warning(f"Failed to capture directory structure: {e}")
        
        return snapshot

    def _format_context_for_prompt(self) -> str:
        """Format context information for the prompt."""
        context_parts = []
        
        # Working directory
        if self.state.working_directory:
            context_parts.append(f"<context name=\"workingDirectory\">\n{self.state.working_directory}\n</context>")
        
        # Directory structure
        if "directory_structure" in self.context_snapshot:
            context_parts.append(f"<context name=\"directoryStructure\">\n{self.context_snapshot['directory_structure']}\n</context>")
        
        # Agent state
        context_parts.append(f"<context name=\"agentState\">\nMode: {self.state.mode.value}\nPhase: {self.state.phase.value}\n</context>")
        
        # Recent actions
        if self.action_history:
            recent_actions = self.action_history[-5:]  # Last 5 actions
            actions_text = "\n".join([
                f"- {action.action_type.value}: {action.content[:100]}{'...' if len(action.content) > 100 else ''}"
                for action in recent_actions
            ])
            context_parts.append(f"<context name=\"recentActions\">\n{actions_text}\n</context>")
        
        return "\n\n".join(context_parts)

    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process a message using the ReAct pattern."""
        # Update context snapshot
        self.context_snapshot = await self._create_context_snapshot()
        
        # Log the action
        self.action_history.append(AgentAction(
            action_type=ActionType.RESPOND,
            content=f"Processing user message: {message[:100]}{'...' if len(message) > 100 else ''}"
        ))
        
        # Build prompt with context
        context_info = self._format_context_for_prompt()
        tool_schemas = self._format_tool_schemas()
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "system", "content": context_info},
            {"role": "system", "content": tool_schemas}
        ]
        
        # Add conversation history (last 10 messages)
        messages.extend(self.conversation_history[-10:])
        messages.append({"role": "user", "content": message})
        
        # Generate response
        full_response = ""
        thinking_content = ""
        
        yield "🤔 Analyzing request...\n\n"
        
        async for chunk in self._generate_response(messages):
            full_response += chunk
            
            # Extract and process thinking content in real-time
            visible_content, current_thinking = self._extract_thinking_content(full_response)
            if current_thinking and current_thinking != thinking_content:
                thinking_content = current_thinking
                # Show thinking progress
                last_line = current_thinking.split('\n')[-1]
                truncated_line = last_line[:80] + ('...' if len(last_line) > 80 else '')
                yield f"💭 {truncated_line}\n"
            
            # Yield visible content
            if visible_content:
                yield chunk
        
        # Log thinking action
        if thinking_content:
            self.action_history.append(AgentAction(
                action_type=ActionType.THINK,
                content=thinking_content
            ))
        
        # Extract and execute tool calls
        tool_calls = self._extract_tool_calls(full_response)
        
        if tool_calls:
            yield "\n\n🎯 **Executing planned actions:**\n\n"
            
            for i, call in enumerate(tool_calls, 1):
                tool_name = call["name"]
                parameters = call["parameters"]
                
                yield f"⏺ **Action {i}**: {tool_name}\n"
                
                # Log tool action
                self.action_history.append(AgentAction(
                    action_type=ActionType.TOOL_USE,
                    content=f"{tool_name} with params: {parameters}",
                    tool_name=tool_name,
                    tool_params=parameters
                ))
                
                # Execute tool
                result = await self._execute_tool_call(tool_name, parameters)
                
                if result.is_success():
                    yield f"⎿ **Completed**: {tool_name}\n"
                    if result.result:
                        # Truncate very long results
                        result_text = str(result.result)
                        if len(result_text) > 1000:
                            result_text = result_text[:997] + "..."
                        yield f"```\n{result_text}\n```\n"
                    
                    # Log observation
                    self.action_history.append(AgentAction(
                        action_type=ActionType.OBSERVE,
                        content=f"Tool {tool_name} succeeded: {str(result.result)[:200]}{'...' if len(str(result.result)) > 200 else ''}"
                    ))
                else:
                    yield f"❌ **Failed**: {tool_name} - {result.error}\n"
                    
                    # Log observation
                    self.action_history.append(AgentAction(
                        action_type=ActionType.OBSERVE,
                        content=f"Tool {tool_name} failed: {result.error}"
                    ))
                
                yield "\n"
        
        # Update conversation history
        self.conversation_history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": full_response}
        ])
        
        # Trim conversation history to prevent unbounded growth
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    async def execute_autonomous_task(self, task: str) -> str:
        """Execute a task autonomously using the ReAct pattern."""
        self.state.mode = AgentMode.AUTONOMOUS
        self.state.phase = ReasoningPhase.ANALYSIS
        
        # Create comprehensive task prompt
        task_prompt = f"""I need to complete this task autonomously: {task}

Please follow the Plan-Act-Observe methodology:

1. **Analyze** the task requirements thoroughly
2. **Plan** a comprehensive approach 
3. **Execute** the plan using available tools
4. **Observe** results and adapt as needed
5. **Summarize** what was accomplished

Use your thinking process to work through this systematically."""
        
        full_response = ""
        async for chunk in self.process_message(task_prompt):
            full_response += chunk
        
        return full_response

    def get_action_summary(self) -> str:
        """Get a summary of recent actions."""
        if not self.action_history:
            return "No actions taken yet."
        
        summary = "## Recent Actions\n\n"
        for action in self.action_history[-10:]:
            timestamp = time.strftime("%H:%M:%S", time.localtime(action.timestamp))
            summary += f"- **{timestamp}** [{action.action_type.value}]: {action.content[:100]}{'...' if len(action.content) > 100 else ''}\n"
        
        return summary

    def clear_context(self) -> None:
        """Clear conversation and action history (like /clear in Claude Code)."""
        self.conversation_history.clear()
        self.action_history.clear()
        self.current_plan.clear()
        self.context_snapshot.clear()
        self.logger.info(f"Cleared context for agent {self.agent_id}")

    def compact_context(self) -> str:
        """Compact conversation history (like /compact in Claude Code)."""
        if len(self.conversation_history) <= 10:
            return "Context is already compact."
        
        # Keep system messages and recent exchanges
        system_messages = [msg for msg in self.conversation_history if msg.get("role") == "system"]
        recent_messages = self.conversation_history[-6:]  # Last 3 exchanges
        
        self.conversation_history = system_messages + recent_messages
        
        return f"Compacted conversation history. Kept {len(system_messages)} system messages and 6 recent messages."