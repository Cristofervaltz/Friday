"""File editing tool for Friday."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EditFileTool(BaseTool):
    """Tool for precise file editing operations.

    Supports:
    - Replacing specific lines
    - Inserting content at position
    - Deleting lines
    - Find/replace patterns

    Safer than overwriting entire files with WriteFileTool.
    """

    def __init__(self, max_file_size: int = 1_000_000) -> None:
        """Initialize EditFileTool.

        Args:
            max_file_size: Maximum file size in bytes (default 1MB).
        """
        self._max_file_size = max_file_size

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Make precise edits to a file. Supports: "
            "replace lines, insert content, delete lines, find/replace patterns."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit (relative or absolute)",
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "replace_lines",
                        "insert_after",
                        "delete_lines",
                        "find_replace",
                    ],
                    "description": (
                        "Edit operation: "
                        "'replace_lines' - replace specific line numbers, "
                        "'insert_after' - insert content after a line, "
                        "'delete_lines' - delete specific lines, "
                        "'find_replace' - find and replace text pattern"
                    ),
                },
                "line_number": {
                    "type": "integer",
                    "description": "Line number (1-indexed) for replace_lines or insert_after",
                },
                "line_numbers": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Line numbers (1-indexed) for delete_lines",
                },
                "content": {
                    "type": "string",
                    "description": "New content for replace_lines or insert_after",
                },
                "find": {
                    "type": "string",
                    "description": "Text pattern to find (for find_replace)",
                },
                "replace": {
                    "type": "string",
                    "description": "Replacement text (for find_replace)",
                },
                "regex": {
                    "type": "boolean",
                    "description": "Use regex for find_replace (default: false)",
                },
                "count": {
                    "type": "integer",
                    "description": "Max replacements for find_replace (default: all)",
                },
            },
            "required": ["path", "operation"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file edit operation.

        Args:
            path: File path to edit.
            operation: Edit operation type.
            line_number: Line number for single-line operations.
            line_numbers: Line numbers for multi-line operations.
            content: New content.
            find: Pattern to find.
            replace: Replacement text.
            regex: Use regex for find/replace.
            count: Max replacements.

        Returns:
            ToolResult with success status or error.
        """
        path_str = kwargs.get("path")
        operation = kwargs.get("operation")

        if not path_str:
            return ToolResult(success=False, error="Missing required parameter: path")

        if not operation:
            return ToolResult(
                success=False, error="Missing required parameter: operation"
            )

        try:
            file_path = Path(path_str).resolve()

            # Security: check if file exists
            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path_str}")

            # Security: check if it's a file
            if not file_path.is_file():
                return ToolResult(
                    success=False, error=f"Path is not a file: {path_str}"
                )

            # Security: check file size
            file_size = file_path.stat().st_size
            if file_size > self._max_file_size:
                return ToolResult(
                    success=False,
                    error=f"File too large: {file_size} bytes (max {self._max_file_size})",
                )

            # Read file
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

            # Execute operation
            if operation == "replace_lines":
                result = self._replace_lines(lines, kwargs)
            elif operation == "insert_after":
                result = self._insert_after(lines, kwargs)
            elif operation == "delete_lines":
                result = self._delete_lines(lines, kwargs)
            elif operation == "find_replace":
                result = self._find_replace(lines, kwargs)
            else:
                return ToolResult(
                    success=False, error=f"Unknown operation: {operation}"
                )

            if not result.success:
                return result

            # Write modified content
            new_content = "".join(result.output)
            file_path.write_text(new_content, encoding="utf-8")

            logger.info(f"Edited file: {file_path} (operation: {operation})")

            return ToolResult(
                success=True, output=f"Successfully edited {file_path} ({operation})"
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"File is not a text file or has invalid encoding: {path_str}",
            )
        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path_str}")
        except Exception as exc:
            logger.exception(f"Failed to edit file: {path_str}")
            return ToolResult(success=False, error=f"Failed to edit file: {exc}")

    def _replace_lines(self, lines: list[str], kwargs: dict[str, Any]) -> ToolResult:
        """Replace specific line with new content."""
        line_number = kwargs.get("line_number")
        content = kwargs.get("content")

        if line_number is None:
            return ToolResult(
                success=False, error="Missing required parameter: line_number"
            )

        if content is None:
            return ToolResult(
                success=False, error="Missing required parameter: content"
            )

        # Convert to 0-indexed
        idx = line_number - 1

        if idx < 0 or idx >= len(lines):
            return ToolResult(
                success=False,
                error=f"Line number {line_number} out of range (file has {len(lines)} lines)",
            )

        # Ensure content ends with newline if original line had one
        if lines[idx].endswith("\n") and not content.endswith("\n"):
            content += "\n"

        lines[idx] = content

        return ToolResult(success=True, output=lines)

    def _insert_after(self, lines: list[str], kwargs: dict[str, Any]) -> ToolResult:
        """Insert content after specified line."""
        line_number = kwargs.get("line_number")
        content = kwargs.get("content")

        if line_number is None:
            return ToolResult(
                success=False, error="Missing required parameter: line_number"
            )

        if content is None:
            return ToolResult(
                success=False, error="Missing required parameter: content"
            )

        # Convert to 0-indexed
        idx = line_number - 1

        if idx < -1 or idx >= len(lines):
            return ToolResult(
                success=False,
                error=f"Line number {line_number} out of range (file has {len(lines)} lines)",
            )

        # Ensure content ends with newline
        if not content.endswith("\n"):
            content += "\n"

        # Insert after specified line (idx + 1)
        lines.insert(idx + 1, content)

        return ToolResult(success=True, output=lines)

    def _delete_lines(self, lines: list[str], kwargs: dict[str, Any]) -> ToolResult:
        """Delete specified lines."""
        line_numbers = kwargs.get("line_numbers")

        if not line_numbers:
            return ToolResult(
                success=False, error="Missing required parameter: line_numbers"
            )

        # Convert to 0-indexed and sort in reverse to delete from end
        indices = sorted([ln - 1 for ln in line_numbers], reverse=True)

        # Validate all indices
        for idx in indices:
            if idx < 0 or idx >= len(lines):
                return ToolResult(
                    success=False,
                    error=f"Line number {idx + 1} out of range (file has {len(lines)} lines)",
                )

        # Delete lines
        for idx in indices:
            del lines[idx]

        return ToolResult(success=True, output=lines)

    def _find_replace(self, lines: list[str], kwargs: dict[str, Any]) -> ToolResult:
        """Find and replace text pattern."""
        find = kwargs.get("find")
        replace = kwargs.get("replace")
        use_regex = kwargs.get("regex", False)
        count = kwargs.get("count", -1)  # -1 means replace all

        if not find:
            return ToolResult(success=False, error="Missing required parameter: find")

        if replace is None:
            return ToolResult(
                success=False, error="Missing required parameter: replace"
            )

        # Join lines, do replacement, split back
        content = "".join(lines)

        try:
            if use_regex:
                if count == -1:
                    new_content = re.sub(find, replace, content)
                else:
                    new_content = re.sub(find, replace, content, count=count)
            else:
                if count == -1:
                    new_content = content.replace(find, replace)
                else:
                    new_content = content.replace(find, replace, count)

            # Split back into lines, preserving line endings
            new_lines = new_content.splitlines(keepends=True)

            return ToolResult(success=True, output=new_lines)

        except re.error as exc:
            return ToolResult(success=False, error=f"Invalid regex pattern: {exc}")
