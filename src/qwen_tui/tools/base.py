"""
Base classes and interfaces for agent tools.

This module provides the foundational classes for implementing Claude Code-style
tools with proper error handling, validation, and result formatting.
"""
import asyncio
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
import json
import tempfile

from ..logging import get_main_logger


class ToolStatus(Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_name: str
    status: ToolStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata or {},
            "execution_time": self.execution_time
        }

    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.status == ToolStatus.COMPLETED and self.error is None


class BaseTool(ABC):
    """Base class for all agent tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = get_main_logger()
        self._working_directory = Path.cwd()

    @property
    def working_directory(self) -> Path:
        """Get the current working directory for this tool."""
        return self._working_directory

    @working_directory.setter
    def working_directory(self, path: Union[str, Path]):
        """Set the working directory for this tool."""
        self._working_directory = Path(path).resolve()

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool's parameters."""
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate parameters against the tool's schema."""
        # Basic validation - can be overridden for more complex validation
        schema = self.get_schema()
        required = schema.get("required", [])
        
        for param in required:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")
        
        return True

    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute the tool with error handling and logging."""
        import time
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing tool: {self.name}", parameters=kwargs)
            self.validate_parameters(kwargs)
            result = await self.execute(**kwargs)
            result.execution_time = time.time() - start_time
            self.logger.info(f"Tool completed: {self.name}", 
                           status=result.status.value,
                           execution_time=result.execution_time)
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            self.logger.error(f"Tool failed: {self.name}", error=error_msg)
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=error_msg,
                execution_time=execution_time
            )


class FileBaseTool(BaseTool):
    """Base class for file-based tools."""
    
    def resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the working directory."""
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return (self.working_directory / path_obj).resolve()

    def validate_file_access(self, path: Path, mode: str = "r") -> None:
        """Validate that a file can be accessed with the given mode."""
        if mode in ("r", "rb"):
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not path.is_file():
                raise IsADirectoryError(f"Path is not a file: {path}")
            if not os.access(path, os.R_OK):
                raise PermissionError(f"No read permission: {path}")
        elif mode in ("w", "wb", "a", "ab"):
            parent = path.parent
            if not parent.exists():
                raise FileNotFoundError(f"Parent directory not found: {parent}")
            if not os.access(parent, os.W_OK):
                raise PermissionError(f"No write permission in directory: {parent}")
        elif mode == "x":
            if path.exists():
                raise FileExistsError(f"File already exists: {path}")
            parent = path.parent
            if not parent.exists():
                raise FileNotFoundError(f"Parent directory not found: {parent}")
            if not os.access(parent, os.W_OK):
                raise PermissionError(f"No write permission in directory: {parent}")


class ProcessBaseTool(BaseTool):
    """Base class for tools that execute external processes."""
    
    def __init__(self, name: str, description: str, timeout: float = 30.0):
        super().__init__(name, description)
        self.timeout = timeout

    async def run_process(
        self,
        command: Union[str, List[str]],
        input_data: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> subprocess.CompletedProcess:
        """Run a subprocess with proper error handling and timeout."""
        if timeout is None:
            timeout = self.timeout

        # Prepare environment
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        try:
            if isinstance(command, str):
                # Use shell for string commands
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdin=subprocess.PIPE if input_data else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.working_directory,
                    env=proc_env
                )
            else:
                # Use exec for list commands
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=subprocess.PIPE if input_data else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.working_directory,
                    env=proc_env
                )

            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_data.encode() if input_data else None),
                timeout=timeout
            )

            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else ""
            )

        except asyncio.TimeoutError:
            if process:
                process.terminate()
                await process.wait()
            raise TimeoutError(f"Command timed out after {timeout} seconds: {command}")
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {command}. Error: {str(e)}")


def create_temp_file(content: str, suffix: str = ".tmp") -> Path:
    """Create a temporary file with given content."""
    fd, path = tempfile.mkstemp(suffix=suffix, text=True)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return Path(path)
    except Exception:
        os.close(fd)
        os.unlink(path)
        raise