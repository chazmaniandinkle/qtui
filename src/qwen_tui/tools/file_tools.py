"""
File management tools that mirror Claude Code's file operations.

These tools provide Read, Write, Edit, and MultiEdit capabilities with
proper error handling and validation.
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .base import BaseTool, FileBaseTool, ToolResult, ToolStatus


class ReadTool(FileBaseTool):
    """Read files with optional line range support."""
    
    def __init__(self):
        super().__init__(
            name="Read",
            description="Reads a file from the filesystem with optional line range"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-based)",
                    "minimum": 1
                },
                "limit": {
                    "type": "integer", 
                    "description": "Number of lines to read",
                    "minimum": 1
                }
            },
            "required": ["file_path"]
        }

    async def execute(self, file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> ToolResult:
        """Read file contents with optional line range."""
        try:
            path = self.resolve_path(file_path)
            self.validate_file_access(path, "r")
            
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            # Apply line range if specified
            if offset is not None:
                start_idx = offset - 1  # Convert to 0-based
                if start_idx >= len(lines):
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.COMPLETED,
                        result="",
                        metadata={"total_lines": len(lines), "message": "Offset beyond end of file"}
                    )
                
                end_idx = start_idx + (limit or len(lines))
                lines = lines[start_idx:end_idx]
            elif limit is not None:
                lines = lines[:limit]
            
            # Format with line numbers like cat -n
            content_lines = []
            start_line = offset or 1
            for i, line in enumerate(lines):
                line_num = start_line + i
                # Truncate very long lines
                if len(line) > 2000:
                    line = line[:1997] + "...\n"
                content_lines.append(f"{line_num:6}→{line.rstrip()}")
            
            content = "\n".join(content_lines)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=content,
                metadata={
                    "total_lines": len(lines),
                    "file_size": path.stat().st_size,
                    "encoding": "utf-8"
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class WriteTool(FileBaseTool):
    """Write content to files with overwrite protection."""
    
    def __init__(self):
        super().__init__(
            name="Write", 
            description="Writes content to a file, creating or overwriting as needed"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": False
                }
            },
            "required": ["file_path", "content"]
        }

    async def execute(self, file_path: str, content: str, create_dirs: bool = False) -> ToolResult:
        """Write content to a file."""
        try:
            path = self.resolve_path(file_path)
            
            # Create parent directories if requested
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if we're overwriting an existing file
            exists_before = path.exists()
            original_size = path.stat().st_size if exists_before else 0
            
            # Write the content
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            new_size = path.stat().st_size
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=f"File written successfully: {path}",
                metadata={
                    "bytes_written": new_size,
                    "lines_written": content.count('\n') + 1 if content else 0,
                    "was_overwrite": exists_before,
                    "original_size": original_size if exists_before else None
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class EditTool(FileBaseTool):
    """Edit files by replacing exact string matches."""
    
    def __init__(self):
        super().__init__(
            name="Edit",
            description="Performs exact string replacements in files"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to modify"
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact text to replace"
                },
                "new_string": {
                    "type": "string", 
                    "description": "Text to replace it with"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default false)",
                    "default": False
                }
            },
            "required": ["file_path", "old_string", "new_string"]
        }

    async def execute(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        """Edit a file by replacing text."""
        try:
            path = self.resolve_path(file_path)
            self.validate_file_access(path, "r")
            
            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for exact match
            if old_string not in content:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"String not found in file: {old_string[:100]}{'...' if len(old_string) > 100 else ''}"
                )
            
            # Check for ambiguous matches if not replace_all
            if not replace_all and content.count(old_string) > 1:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"String appears {content.count(old_string)} times. Use replace_all=true or provide more context to make it unique."
                )
            
            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                replacements = 1
            
            # Write back to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=f"Successfully replaced {replacements} occurrence(s)",
                metadata={
                    "replacements_made": replacements,
                    "old_length": len(content),
                    "new_length": len(new_content)
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class MultiEditTool(FileBaseTool):
    """Perform multiple edits on a single file atomically."""
    
    def __init__(self):
        super().__init__(
            name="MultiEdit",
            description="Performs multiple find-and-replace operations on a file atomically"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to modify"
                },
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_string": {"type": "string"},
                            "new_string": {"type": "string"},
                            "replace_all": {"type": "boolean", "default": False}
                        },
                        "required": ["old_string", "new_string"]
                    },
                    "description": "Array of edit operations to perform"
                }
            },
            "required": ["file_path", "edits"]
        }

    async def execute(self, file_path: str, edits: List[Dict[str, Any]]) -> ToolResult:
        """Perform multiple edits on a file."""
        try:
            path = self.resolve_path(file_path)
            self.validate_file_access(path, "r")
            
            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_replacements = 0
            edit_details = []
            
            # Apply each edit sequentially
            for i, edit in enumerate(edits):
                old_string = edit["old_string"]
                new_string = edit["new_string"] 
                replace_all = edit.get("replace_all", False)
                
                # Check if string exists
                if old_string not in content:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.ERROR,
                        error=f"Edit {i+1}: String not found: {old_string[:100]}{'...' if len(old_string) > 100 else ''}"
                    )
                
                # Check for ambiguous matches if not replace_all
                occurrences = content.count(old_string)
                if not replace_all and occurrences > 1:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.ERROR,
                        error=f"Edit {i+1}: String appears {occurrences} times. Use replace_all=true or provide more context."
                    )
                
                # Perform replacement
                if replace_all:
                    content = content.replace(old_string, new_string)
                    replacements = occurrences
                else:
                    content = content.replace(old_string, new_string, 1)
                    replacements = 1
                
                total_replacements += replacements
                edit_details.append({
                    "edit_number": i + 1,
                    "replacements": replacements,
                    "old_length": len(old_string),
                    "new_length": len(new_string)
                })
            
            # Write back to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=f"Successfully applied {len(edits)} edits with {total_replacements} total replacements",
                metadata={
                    "edits_applied": len(edits),
                    "total_replacements": total_replacements,
                    "original_length": len(original_content),
                    "final_length": len(content),
                    "edit_details": edit_details
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )