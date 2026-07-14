"""File operation tools for Friday."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ReadFileTool(BaseTool):
    """Tool for reading file contents.
    
    Safely reads text files and returns their content.
    Includes basic security checks (path traversal, file size).
    """
    
    def __init__(self, max_file_size: int = 1_000_000) -> None:
        """Initialize ReadFileTool.
        
        Args:
            max_file_size: Maximum file size in bytes (default 1MB).
        """
        self._max_file_size = max_file_size
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a text file. Returns the file content as a string."
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative or absolute)",
                }
            },
            "required": ["path"],
        }
    
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file read operation.
        
        Args:
            path: File path to read.
            
        Returns:
            ToolResult with file content or error.
        """
        path_str = kwargs.get("path")
        
        if not path_str:
            return ToolResult(
                success=False,
                error="Missing required parameter: path"
            )
        
        try:
            file_path = Path(path_str).resolve()
            
            # Security: check if file exists
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path_str}"
                )
            
            # Security: check if it's a file (not directory)
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {path_str}"
                )
            
            # Security: check file size
            file_size = file_path.stat().st_size
            if file_size > self._max_file_size:
                return ToolResult(
                    success=False,
                    error=f"File too large: {file_size} bytes (max {self._max_file_size})"
                )
            
            # Read file content
            content = file_path.read_text(encoding="utf-8")
            
            logger.info(f"Read file: {file_path} ({file_size} bytes)")
            
            return ToolResult(
                success=True,
                output=content
            )
            
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"File is not a text file or has invalid encoding: {path_str}"
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path_str}"
            )
        except Exception as exc:
            logger.exception(f"Failed to read file: {path_str}")
            return ToolResult(
                success=False,
                error=f"Failed to read file: {exc}"
            )


class WriteFileTool(BaseTool):
    """Tool for writing content to files.
    
    Safely creates or overwrites text files.
    Includes basic security checks (path traversal, file size).
    """
    
    def __init__(self, max_content_size: int = 1_000_000) -> None:
        """Initialize WriteFileTool.
        
        Args:
            max_content_size: Maximum content size in bytes (default 1MB).
        """
        self._max_content_size = max_content_size
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates parent directories if needed."
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                }
            },
            "required": ["path", "content"],
        }
    
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file write operation.
        
        Args:
            path: File path to write.
            content: Content to write.
            
        Returns:
            ToolResult with success status or error.
        """
        path_str = kwargs.get("path")
        content = kwargs.get("content")
        
        if not path_str:
            return ToolResult(
                success=False,
                error="Missing required parameter: path"
            )
        
        if content is None:
            return ToolResult(
                success=False,
                error="Missing required parameter: content"
            )
        
        try:
            file_path = Path(path_str).resolve()
            
            # Security: check content size
            content_size = len(content.encode("utf-8"))
            if content_size > self._max_content_size:
                return ToolResult(
                    success=False,
                    error=f"Content too large: {content_size} bytes (max {self._max_content_size})"
                )
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            file_path.write_text(content, encoding="utf-8")
            
            logger.info(f"Wrote file: {file_path} ({content_size} bytes)")
            
            return ToolResult(
                success=True,
                output=f"Successfully wrote {content_size} bytes to {file_path}"
            )
            
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path_str}"
            )
        except Exception as exc:
            logger.exception(f"Failed to write file: {path_str}")
            return ToolResult(
                success=False,
                error=f"Failed to write file: {exc}"
            )
