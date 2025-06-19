"""
Execution tools for running commands and delegating tasks.

These tools provide Bash execution and Task delegation capabilities.
"""
import asyncio
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseTool, ProcessBaseTool, ToolResult, ToolStatus


class BashTool(ProcessBaseTool):
    """Execute bash commands with proper security and error handling."""
    
    def __init__(self):
        super().__init__(
            name="Bash",
            description="Executes bash commands in a persistent shell session",
            timeout=120.0  # 2 minutes default timeout
        )
        self._shell_env = os.environ.copy()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (max 600)",
                    "maximum": 600,
                    "default": 120
                },
                "description": {
                    "type": "string",
                    "description": "Clear description of what this command does"
                },
                "env": {
                    "type": "object",
                    "description": "Environment variables to set",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["command"]
        }

    def _validate_command(self, command: str) -> None:
        """Validate command for basic security."""
        # Block dangerous commands
        dangerous_patterns = [
            r'\brm\s+-rf\s+/',  # rm -rf /
            r'\bdd\s+',  # dd command
            r'>\s*/dev/null.*2>&1.*&',  # Background processes that might hide output
            r'\bsudo\s+',  # sudo commands
            r'\bsu\s+',  # su commands
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValueError(f"Potentially dangerous command detected: {command}")

    def _format_output(self, result: subprocess.CompletedProcess) -> str:
        """Format command output for display."""
        output_parts = []
        
        if result.stdout:
            output_parts.append(result.stdout.strip())
        
        if result.stderr:
            stderr_text = result.stderr.strip()
            if stderr_text:
                output_parts.append(f"STDERR:\n{stderr_text}")
        
        return "\n".join(output_parts) if output_parts else ""

    async def execute(self, command: str, timeout: Optional[float] = None, 
                     description: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> ToolResult:
        """Execute a bash command."""
        try:
            # Validate command
            self._validate_command(command)
            
            # Set timeout
            if timeout is None:
                timeout = self.timeout
            elif timeout > 600:
                timeout = 600  # Max 10 minutes
            
            # Prepare environment
            command_env = self._shell_env.copy()
            if env:
                command_env.update(env)
            
            # Log command execution
            self.logger.info(f"Executing command: {command}", 
                           description=description, 
                           timeout=timeout)
            
            # Execute command
            result = await self.run_process(
                command, 
                timeout=timeout, 
                env=command_env
            )
            
            # Format output
            output = self._format_output(result)
            
            # Determine status
            if result.returncode == 0:
                status = ToolStatus.COMPLETED
                error = None
            else:
                status = ToolStatus.ERROR
                error = f"Command failed with exit code {result.returncode}"
                if result.stderr:
                    error += f": {result.stderr.strip()}"
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                result=output,
                error=error,
                metadata={
                    "command": command,
                    "exit_code": result.returncode,
                    "description": description,
                    "timeout": timeout
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e),
                metadata={
                    "command": command,
                    "description": description
                }
            )


class TaskTool(BaseTool):
    """Delegate complex tasks to specialized agents."""
    
    def __init__(self):
        super().__init__(
            name="Task",
            description="Launch specialized agents for complex tasks"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short description of the task (3-5 words)"
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed task description for the agent"
                },
                "task_type": {
                    "type": "string",
                    "enum": ["search", "analysis", "coding", "debugging", "research"],
                    "description": "Type of task to optimize agent behavior",
                    "default": "analysis"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for the task",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Relevant files for the task"
                        },
                        "keywords": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "description": "Keywords related to the task"
                        }
                    }
                }
            },
            "required": ["description", "prompt"]
        }

    async def execute(self, description: str, prompt: str, task_type: str = "analysis",
                     context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute a task using a specialized agent."""
        try:
            # For now, simulate task delegation
            # In a real implementation, this would spawn a new agent instance
            
            # Validate inputs
            if len(description) > 100:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error="Description too long (max 100 characters)"
                )
            
            if len(prompt) < 10:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error="Prompt too short (min 10 characters)"
                )
            
            # Create task summary
            task_summary = f"Task: {description}\n"
            task_summary += f"Type: {task_type}\n"
            task_summary += f"Prompt: {prompt}\n"
            
            if context:
                if context.get("files"):
                    task_summary += f"Files: {', '.join(context['files'])}\n"
                if context.get("keywords"):
                    task_summary += f"Keywords: {', '.join(context['keywords'])}\n"
            
            # Simulate task execution
            await asyncio.sleep(0.1)  # Simulate processing time
            
            result_message = f"Task '{description}' queued for execution.\n"
            result_message += "This is a placeholder - in production, this would delegate to a specialized agent.\n"
            result_message += f"Task type: {task_type}\n"
            result_message += f"Prompt length: {len(prompt)} characters"
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_message,
                metadata={
                    "description": description,
                    "task_type": task_type,
                    "prompt_length": len(prompt),
                    "context": context or {}
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class NotebookTool(BaseTool):
    """Execute code in notebook environments."""
    
    def __init__(self):
        super().__init__(
            name="NotebookExecute",
            description="Execute code in Jupyter notebook environments"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code to execute in the notebook kernel"
                },
                "kernel_type": {
                    "type": "string",
                    "enum": ["python", "python3", "javascript", "r"],
                    "description": "Kernel type for execution",
                    "default": "python3"
                },
                "timeout": {
                    "type": "number",
                    "description": "Execution timeout in seconds",
                    "default": 30
                }
            },
            "required": ["code"]
        }

    async def execute(self, code: str, kernel_type: str = "python3", timeout: float = 30) -> ToolResult:
        """Execute code in a notebook kernel."""
        try:
            # For now, simulate notebook execution
            # In a real implementation, this would use jupyter client
            
            if not code.strip():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error="No code provided"
                )
            
            # Simulate execution
            await asyncio.sleep(0.1)
            
            result_message = f"Code executed in {kernel_type} kernel:\n"
            result_message += f"```{kernel_type}\n{code}\n```\n"
            result_message += "This is a placeholder - in production, this would execute in a real kernel."
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_message,
                metadata={
                    "kernel_type": kernel_type,
                    "code_length": len(code),
                    "timeout": timeout
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )