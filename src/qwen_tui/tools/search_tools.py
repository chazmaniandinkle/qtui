"""
Code analysis and search tools that mirror Claude Code's capabilities.

These tools provide Grep, Glob, and LS functionality for codebase exploration.
"""
import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .base import BaseTool, FileBaseTool, ToolResult, ToolStatus


class GrepTool(FileBaseTool):
    """Search file contents using regular expressions."""
    
    def __init__(self):
        super().__init__(
            name="Grep",
            description="Fast content search using regular expressions"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to current directory)"
                },
                "include": {
                    "type": "string",
                    "description": "File pattern to include (e.g., '*.py', '*.{ts,tsx}')"
                },
                "exclude": {
                    "type": "string",
                    "description": "File pattern to exclude"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100
                }
            },
            "required": ["pattern"]
        }

    def _should_include_file(self, file_path: Path, include: Optional[str], exclude: Optional[str]) -> bool:
        """Check if a file should be included based on include/exclude patterns."""
        name = file_path.name
        
        # Check exclude first
        if exclude and fnmatch.fnmatch(name, exclude):
            return False
        
        # Check include
        if include:
            # Handle multiple extensions like "*.{ts,tsx}"
            if '{' in include and '}' in include:
                base_pattern = include.split('{')[0]
                extensions = include.split('{')[1].split('}')[0].split(',')
                for ext in extensions:
                    if fnmatch.fnmatch(name, base_pattern + ext):
                        return True
                return False
            else:
                return fnmatch.fnmatch(name, include)
        
        return True

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if a file is likely a text file."""
        if file_path.suffix.lower() in {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', 
                                        '.cs', '.php', '.rb', '.go', '.rs', '.kt', '.swift', '.scala',
                                        '.html', '.css', '.scss', '.less', '.xml', '.json', '.yaml', '.yml',
                                        '.md', '.txt', '.cfg', '.conf', '.ini', '.log', '.sql', '.sh', '.bat',
                                        '.dockerfile', '.makefile', '.cmake', '.gradle', '.properties'}:
            return True
        
        # Check for files without extensions that might be text
        if not file_path.suffix:
            try:
                with open(file_path, 'rb') as f:
                    sample = f.read(512)
                    # Check if it's mostly text
                    text_chars = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13))
                    return text_chars / len(sample) > 0.7 if sample else False
            except:
                return False
        
        return False

    async def execute(self, pattern: str, path: Optional[str] = None, include: Optional[str] = None, 
                     exclude: Optional[str] = None, max_results: int = 100) -> ToolResult:
        """Search for pattern in file contents."""
        try:
            search_path = self.resolve_path(path or ".")
            if not search_path.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Path does not exist: {search_path}"
                )
            
            # Compile regex pattern
            try:
                regex = re.compile(pattern, re.MULTILINE)
            except re.error as e:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Invalid regex pattern: {e}"
                )
            
            matches = []
            files_searched = 0
            
            # Walk through directory tree
            if search_path.is_file():
                files_to_search = [search_path]
            else:
                files_to_search = [f for f in search_path.rglob("*") if f.is_file()]
            
            for file_path in files_to_search:
                if len(matches) >= max_results:
                    break
                
                # Skip files based on patterns
                if not self._should_include_file(file_path, include, exclude):
                    continue
                
                # Skip non-text files
                if not self._is_text_file(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if regex.search(content):
                        relative_path = file_path.relative_to(self.working_directory)
                        matches.append(str(relative_path))
                    
                    files_searched += 1
                    
                except (UnicodeDecodeError, PermissionError):
                    # Skip files we can't read
                    continue
            
            # Sort matches by modification time (most recent first)
            matches.sort(key=lambda x: self.resolve_path(x).stat().st_mtime, reverse=True)
            
            result_text = "\n".join(matches) if matches else "No matches found"
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_text,
                metadata={
                    "matches_found": len(matches),
                    "files_searched": files_searched,
                    "pattern": pattern,
                    "search_path": str(search_path)
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class GlobTool(FileBaseTool):
    """Fast file pattern matching."""
    
    def __init__(self):
        super().__init__(
            name="Glob",
            description="Fast file pattern matching with glob patterns"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files against (e.g., '**/*.py', 'src/**/*.ts')"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to current directory)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 200
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, pattern: str, path: Optional[str] = None, max_results: int = 200) -> ToolResult:
        """Find files matching glob pattern."""
        try:
            search_path = self.resolve_path(path or ".")
            if not search_path.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Path does not exist: {search_path}"
                )
            
            # Use pathlib's glob functionality
            if pattern.startswith('/'):
                # Absolute pattern
                matches = list(Path(pattern).parent.glob(Path(pattern).name))
            else:
                # Relative pattern
                matches = list(search_path.glob(pattern))
            
            # Sort by modification time (most recent first)
            matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Limit results
            matches = matches[:max_results]
            
            # Convert to relative paths
            relative_matches = []
            for match in matches:
                try:
                    relative_path = match.relative_to(self.working_directory)
                    relative_matches.append(str(relative_path))
                except ValueError:
                    # If can't make relative, use absolute
                    relative_matches.append(str(match))
            
            result_text = "\n".join(relative_matches) if relative_matches else "No matches found"
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_text,
                metadata={
                    "matches_found": len(relative_matches),
                    "pattern": pattern,
                    "search_path": str(search_path)
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )


class LSTool(FileBaseTool):
    """List files and directories."""
    
    def __init__(self):
        super().__init__(
            name="LS",
            description="Lists files and directories with optional filtering"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to directory to list"
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of glob patterns to ignore"
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files (starting with .)",
                    "default": False
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List directories recursively",
                    "default": False
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum recursion depth",
                    "default": 3
                }
            },
            "required": ["path"]
        }

    def _should_ignore(self, path: Path, ignore_patterns: List[str]) -> bool:
        """Check if a path should be ignored based on patterns."""
        name = path.name
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _format_entry(self, path: Path, base_path: Path, depth: int = 0) -> str:
        """Format a directory entry for display."""
        try:
            relative_path = path.relative_to(base_path)
            indent = "  " * depth
            
            if path.is_dir():
                return f"{indent}- {relative_path}/"
            else:
                return f"{indent}  - {relative_path}"
        except ValueError:
            # If can't make relative, use name
            indent = "  " * depth
            if path.is_dir():
                return f"{indent}- {path.name}/"
            else:
                return f"{indent}  - {path.name}"

    async def execute(self, path: str, ignore: Optional[List[str]] = None, show_hidden: bool = False,
                     recursive: bool = False, max_depth: int = 3) -> ToolResult:
        """List directory contents."""
        try:
            list_path = Path(path).resolve()
            if not list_path.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Path does not exist: {list_path}"
                )
            
            if not list_path.is_dir():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Path is not a directory: {list_path}"
                )
            
            ignore_patterns = ignore or []
            entries = []
            
            def list_directory(dir_path: Path, current_depth: int = 0):
                if current_depth > max_depth:
                    return
                
                try:
                    items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                    
                    for item in items:
                        # Skip hidden files unless requested
                        if not show_hidden and item.name.startswith('.'):
                            continue
                        
                        # Skip ignored patterns
                        if self._should_ignore(item, ignore_patterns):
                            continue
                        
                        entries.append(self._format_entry(item, list_path, current_depth))
                        
                        # Recurse into directories if requested
                        if recursive and item.is_dir() and current_depth < max_depth:
                            list_directory(item, current_depth + 1)
                
                except PermissionError:
                    entries.append(f"{'  ' * current_depth}[Permission Denied]")
            
            # Add the root directory
            entries.append(f"- {list_path}/")
            list_directory(list_path)
            
            result_text = "\n".join(entries)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.COMPLETED,
                result=result_text,
                metadata={
                    "entries_found": len(entries) - 1,  # Subtract root directory
                    "path": str(list_path),
                    "recursive": recursive,
                    "max_depth": max_depth
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error=str(e)
            )