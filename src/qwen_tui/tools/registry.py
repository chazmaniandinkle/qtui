"""
Tool registry and manager for the agent system.

Provides centralized tool management, validation, and execution.
"""
import asyncio
from typing import Any, Dict, List, Optional, Type, Union
import json

from .base import BaseTool, ToolResult, ToolStatus
from .file_tools import ReadTool, WriteTool, EditTool, MultiEditTool
from .search_tools import GrepTool, GlobTool, LSTool
from .execution_tools import BashTool, TaskTool, NotebookTool
from ..logging import get_main_logger

# Import permission system for runtime checking
def _get_permission_manager():
    """Lazy import to avoid circular dependencies."""
    try:
        from ..tui.permission_manager import get_tui_permission_manager
        return get_tui_permission_manager()
    except ImportError:
        return None


class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        self.logger = get_main_logger()
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_default_tools()

    def _initialize_default_tools(self):
        """Initialize the default tool set."""
        default_tools = [
            # File management tools
            ReadTool(),
            WriteTool(),
            EditTool(),
            MultiEditTool(),
            
            # Search and analysis tools
            GrepTool(),
            GlobTool(),
            LSTool(),
            
            # Execution tools
            BashTool(),
            TaskTool(),
            NotebookTool(),
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
        
        self.logger.info(f"Initialized tool registry with {len(self._tools)} tools")

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool in the registry."""
        if tool.name in self._tools:
            self.logger.warning(f"Tool {tool.name} is being replaced")
        
        self._tools[tool.name] = tool
        self.logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """Get list of all available tool names."""
        return list(self._tools.keys())

    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get schemas for all tools."""
        schemas = {}
        for name, tool in self._tools.items():
            schemas[name] = {
                "name": name,
                "description": tool.description,
                "parameters": tool.get_schema()
            }
        return schemas

    def get_openai_function_schemas(self) -> List[Dict[str, Any]]:
        """Get tool schemas in OpenAI function calling format."""
        functions = []
        for name, tool in self._tools.items():
            functions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.get_schema()
                }
            })
        return functions

    async def execute_tool(self, name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given parameters."""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                tool_name=name,
                status=ToolStatus.ERROR,
                error=f"Tool not found: {name}"
            )
        
        # Check permissions if permission manager is available
        permission_manager = _get_permission_manager()
        if permission_manager:
            try:
                permission_result = await permission_manager.request_permission(name, parameters)
                if not permission_result.allowed:
                    error_msg = "Permission denied"
                    if permission_result.user_cancelled:
                        error_msg = "Operation cancelled by user"
                    return ToolResult(
                        tool_name=name,
                        status=ToolStatus.ERROR,
                        error=error_msg
                    )
            except Exception as e:
                self.logger.error("Permission check failed", tool=name, error=str(e))
                # Fail safe - deny on permission error
                return ToolResult(
                    tool_name=name,
                    status=ToolStatus.ERROR,
                    error=f"Permission check failed: {str(e)}"
                )
        
        return await tool.safe_execute(**parameters)


class ToolManager:
    """Manages tool execution and coordination for agents."""
    
    def __init__(self, working_directory: Optional[str] = None):
        self.registry = ToolRegistry()
        self.logger = get_main_logger()
        self.working_directory = working_directory
        self._execution_history: List[Dict[str, Any]] = []

    def set_working_directory(self, path: str) -> None:
        """Set working directory for all tools."""
        self.working_directory = path
        for tool in self.registry._tools.values():
            if hasattr(tool, 'working_directory'):
                tool.working_directory = path
        
        self.logger.info(f"Set working directory: {path}")

    async def execute_tool_sequence(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute a sequence of tool calls."""
        results = []
        
        for call in tool_calls:
            tool_name = call.get("name") or call.get("tool_name")
            parameters = call.get("parameters", {})
            
            if not tool_name:
                result = ToolResult(
                    tool_name="unknown",
                    status=ToolStatus.ERROR,
                    error="Missing tool name in call"
                )
            else:
                result = await self.registry.execute_tool(tool_name, parameters)
            
            results.append(result)
            
            # Log execution
            self._execution_history.append({
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result.to_dict(),
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Stop on error if not continuing
            if result.status == ToolStatus.ERROR and not call.get("continue_on_error", False):
                self.logger.warning(f"Tool sequence stopped due to error in {tool_name}")
                break
        
        return results

    async def execute_parallel_tools(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute multiple tools in parallel."""
        tasks = []
        
        for call in tool_calls:
            tool_name = call.get("name") or call.get("tool_name")
            parameters = call.get("parameters", {})
            
            if tool_name:
                task = self.registry.execute_tool(tool_name, parameters)
                tasks.append(task)
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ToolResult(
                    tool_name=tool_calls[i].get("name", "unknown"),
                    status=ToolStatus.ERROR,
                    error=str(result)
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        return final_results

    def get_tool_suggestions(self, query: str) -> List[str]:
        """Get tool suggestions based on a query."""
        query_lower = query.lower()
        suggestions = []
        
        # Simple keyword matching
        tool_keywords = {
            "read": ["ReadTool"],
            "write": ["WriteTool"], 
            "edit": ["EditTool", "MultiEditTool"],
            "search": ["GrepTool", "GlobTool"],
            "find": ["GrepTool", "GlobTool"],
            "list": ["LSTool"],
            "directory": ["LSTool"],
            "run": ["BashTool"],
            "execute": ["BashTool", "NotebookTool"],
            "command": ["BashTool"],
            "task": ["TaskTool"],
            "delegate": ["TaskTool"]
        }
        
        for keyword, tools in tool_keywords.items():
            if keyword in query_lower:
                suggestions.extend(tools)
        
        # Remove duplicates and return
        return list(set(suggestions))

    def get_execution_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent tool execution history."""
        history = self._execution_history.copy()
        if limit:
            history = history[-limit:]
        return history

    def clear_history(self) -> None:
        """Clear execution history."""
        self._execution_history.clear()
        self.logger.info("Cleared tool execution history")

    def get_tool_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for tools."""
        stats = {}
        for entry in self._execution_history:
            tool_name = entry["tool_name"]
            if tool_name not in stats:
                stats[tool_name] = {
                    "executions": 0,
                    "successes": 0,
                    "errors": 0,
                    "total_time": 0.0
                }
            
            stats[tool_name]["executions"] += 1
            result = entry["result"]
            
            if result.get("status") == "completed":
                stats[tool_name]["successes"] += 1
            elif result.get("status") == "error":
                stats[tool_name]["errors"] += 1
            
            exec_time = result.get("execution_time", 0)
            if exec_time:
                stats[tool_name]["total_time"] += exec_time
        
        return stats


# Global tool manager instance
_global_tool_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Get the global tool manager instance."""
    global _global_tool_manager
    if _global_tool_manager is None:
        _global_tool_manager = ToolManager()
    return _global_tool_manager


def set_global_working_directory(path: str) -> None:
    """Set working directory for the global tool manager."""
    manager = get_tool_manager()
    manager.set_working_directory(path)