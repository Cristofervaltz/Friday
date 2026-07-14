"""Directory listing tool for Friday."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ListFilesTool(BaseTool):
    """Tool for listing files and directories.
    
    Provides directory exploration with filtering and recursion options.
    Useful for understanding project structure.
    """
    
    def __init__(self, max_entries: int = 1000) -> None:
        """Initialize ListFilesTool.
        
        Args:
            max_entries: Maximum number of entries to return (default 1000).
        """
        self._max_entries = max_entries
    
    @property
    def name(self) -> str:
        return "list_files"
    
    @property
    def description(self) -> str:
        return (
            "List files and directories. Supports pattern filtering "
            "(*.py, *.txt), recursive listing, and sorting by name/size/date."
        )
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.txt')",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List files recursively in subdirectories",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files (starting with .)",
                },
                "show_details": {
                    "type": "boolean",
                    "description": "Show file sizes and modification dates",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "size", "date"],
                    "description": "Sort results by name, size, or modification date",
                },
            },
            "required": [],
        }
    
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute directory listing.
        
        Args:
            path: Directory path (default: current directory).
            pattern: Glob pattern for filtering.
            recursive: List recursively.
            show_hidden: Include hidden files.
            show_details: Show file sizes and dates.
            sort_by: Sort order (name/size/date).
            
        Returns:
            ToolResult with file listing or error.
        """
        path_str = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")
        recursive = kwargs.get("recursive", False)
        show_hidden = kwargs.get("show_hidden", False)
        show_details = kwargs.get("show_details", False)
        sort_by = kwargs.get("sort_by", "name")
        
        try:
            dir_path = Path(path_str).resolve()
            
            # Security: check if directory exists
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path_str}"
                )
            
            # Security: check if it's a directory
            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path_str}"
                )
            
            # Get file list
            if recursive:
                glob_pattern = f"**/{pattern}"
                entries = list(dir_path.glob(glob_pattern))
            else:
                entries = list(dir_path.glob(pattern))
            
            # Filter hidden files
            if not show_hidden:
                entries = [e for e in entries if not e.name.startswith(".")]
            
            # Limit results
            if len(entries) > self._max_entries:
                return ToolResult(
                    success=False,
                    error=f"Too many entries: {len(entries)} (max {self._max_entries}). Use pattern or recursive=false to narrow down."
                )
            
            # Sort entries
            if sort_by == "size":
                entries.sort(key=lambda e: e.stat().st_size if e.is_file() else 0, reverse=True)
            elif sort_by == "date":
                entries.sort(key=lambda e: e.stat().st_mtime, reverse=True)
            else:  # name
                entries.sort(key=lambda e: e.name.lower())
            
            # Format output
            output_lines = [f"📁 {dir_path}\n"]
            
            if not entries:
                output_lines.append("(empty)")
            else:
                for entry in entries:
                    output_lines.append(self._format_entry(entry, dir_path, show_details))
            
            output = "\n".join(output_lines)
            
            logger.info(f"Listed directory: {dir_path} ({len(entries)} entries)")
            
            return ToolResult(
                success=True,
                output=output
            )
            
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path_str}"
            )
        except Exception as exc:
            logger.exception(f"Failed to list directory: {path_str}")
            return ToolResult(
                success=False,
                error=f"Failed to list directory: {exc}"
            )
    
    def _format_entry(self, entry: Path, base_path: Path, show_details: bool) -> str:
        """Format a single directory entry.
        
        Args:
            entry: Path entry to format.
            base_path: Base directory path.
            show_details: Whether to show size and date.
            
        Returns:
            Formatted string.
        """
        # Get relative path
        try:
            rel_path = entry.relative_to(base_path)
        except ValueError:
            rel_path = entry
        
        # Entry type icon
        if entry.is_dir():
            icon = "📁"
            size_str = "<DIR>"
        elif entry.is_file():
            icon = "📄"
            size_str = self._format_size(entry.stat().st_size) if show_details else ""
        else:
            icon = "🔗"  # symlink or other
            size_str = "<LINK>"
        
        # Format line
        if show_details and entry.is_file():
            mtime = entry.stat().st_mtime
            import datetime
            date_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            return f"{icon} {rel_path}  ({size_str}, {date_str})"
        elif show_details:
            return f"{icon} {rel_path}  {size_str}"
        else:
            return f"{icon} {rel_path}"
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format.
        
        Args:
            size: File size in bytes.
            
        Returns:
            Formatted size string.
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
