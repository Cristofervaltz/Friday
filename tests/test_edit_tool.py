"""Tests for EditFileTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tools import EditFileTool


@pytest.fixture
def edit_tool() -> EditFileTool:
    """Create EditFileTool instance."""
    return EditFileTool()


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file for testing."""
    file_path = tmp_path / "test.txt"
    content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_edit_tool_has_correct_name(edit_tool: EditFileTool) -> None:
    """Test that EditFileTool has the correct name."""
    assert edit_tool.name == "edit_file"


def test_edit_tool_has_description(edit_tool: EditFileTool) -> None:
    """Test that EditFileTool has a description."""
    assert len(edit_tool.description) > 0
    assert "edit" in edit_tool.description.lower()


def test_edit_tool_has_parameters_schema(edit_tool: EditFileTool) -> None:
    """Test that EditFileTool has a parameters schema."""
    schema = edit_tool.parameters_schema
    assert schema["type"] == "object"
    assert "path" in schema["properties"]
    assert "operation" in schema["properties"]


def test_replace_lines_operation(edit_tool: EditFileTool, sample_file: Path) -> None:
    """Test replace_lines operation."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="replace_lines",
        line_number=2,
        content="New Line 2",
    )

    assert result.success

    # Verify file was modified
    lines = sample_file.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "New Line 2"  # Line 2 was replaced
    assert lines[0] == "Line 1"  # Line 1 unchanged
    assert lines[2] == "Line 3"  # Line 3 unchanged


def test_insert_after_operation(edit_tool: EditFileTool, sample_file: Path) -> None:
    """Test insert_after operation."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="insert_after",
        line_number=2,
        content="Inserted Line",
    )

    assert result.success

    # Verify line was inserted
    lines = sample_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6  # 5 original + 1 inserted
    assert lines[2] == "Inserted Line"


def test_delete_lines_operation(edit_tool: EditFileTool, sample_file: Path) -> None:
    """Test delete_lines operation."""
    result = edit_tool.execute(
        path=str(sample_file), operation="delete_lines", line_numbers=[2, 4]
    )

    assert result.success

    # Verify lines were deleted
    lines = sample_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # 5 original - 2 deleted
    assert "Line 2" not in lines
    assert "Line 4" not in lines
    assert "Line 1" in lines
    assert "Line 3" in lines
    assert "Line 5" in lines


def test_find_replace_operation_simple(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test find_replace operation with simple text."""
    result = edit_tool.execute(
        path=str(sample_file), operation="find_replace", find="Line", replace="Row"
    )

    assert result.success

    # Verify text was replaced
    content = sample_file.read_text(encoding="utf-8")
    assert "Row 1" in content
    assert "Row 2" in content
    assert "Line" not in content


def test_find_replace_operation_with_regex(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test find_replace operation with regex."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="find_replace",
        find=r"Line (\d+)",
        replace=r"Item \1",
        regex=True,
    )

    assert result.success

    # Verify regex replacement worked
    content = sample_file.read_text(encoding="utf-8")
    assert "Item 1" in content
    assert "Item 2" in content
    assert "Line" not in content


def test_find_replace_with_count_limit(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test find_replace operation with count limit."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="find_replace",
        find="Line",
        replace="Row",
        count=2,
    )

    assert result.success

    # Verify only 2 replacements were made
    content = sample_file.read_text(encoding="utf-8")
    assert content.count("Row") == 2
    assert content.count("Line") == 3  # Remaining 3


def test_file_not_found_error(edit_tool: EditFileTool, tmp_path: Path) -> None:
    """Test error handling for non-existent file."""
    result = edit_tool.execute(
        path=str(tmp_path / "nonexistent.txt"),
        operation="replace_lines",
        line_number=1,
        content="Test",
    )

    assert not result.success
    assert "not found" in result.error.lower()


def test_line_number_out_of_range_error(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test error handling for line number out of range."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="replace_lines",
        line_number=100,
        content="Test",
    )

    assert not result.success
    assert "out of range" in result.error.lower()


def test_missing_required_parameter_path(edit_tool: EditFileTool) -> None:
    """Test error handling for missing path parameter."""
    result = edit_tool.execute(operation="replace_lines", line_number=1, content="Test")

    assert not result.success
    assert "path" in result.error.lower()


def test_missing_required_parameter_operation(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test error handling for missing operation parameter."""
    result = edit_tool.execute(path=str(sample_file))

    assert not result.success
    assert "operation" in result.error.lower()


def test_invalid_operation(edit_tool: EditFileTool, sample_file: Path) -> None:
    """Test error handling for invalid operation."""
    result = edit_tool.execute(path=str(sample_file), operation="invalid_op")

    assert not result.success
    assert "unknown" in result.error.lower()


def test_file_too_large_error(tmp_path: Path) -> None:
    """Test error handling for files exceeding size limit."""
    tool = EditFileTool(max_file_size=100)  # Very small limit

    large_file = tmp_path / "large.txt"
    large_file.write_text("x" * 1000, encoding="utf-8")

    result = tool.execute(
        path=str(large_file), operation="replace_lines", line_number=1, content="Test"
    )

    assert not result.success
    assert "too large" in result.error.lower()


def test_invalid_regex_pattern(edit_tool: EditFileTool, sample_file: Path) -> None:
    """Test error handling for invalid regex pattern."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="find_replace",
        find="[invalid",  # Unclosed bracket
        replace="test",
        regex=True,
    )

    assert not result.success
    assert "regex" in result.error.lower()


def test_delete_multiple_lines_in_reverse_order(
    edit_tool: EditFileTool, sample_file: Path
) -> None:
    """Test that delete_lines handles multiple lines correctly."""
    result = edit_tool.execute(
        path=str(sample_file),
        operation="delete_lines",
        line_numbers=[5, 3, 1],  # Intentionally out of order
    )

    assert result.success

    # Verify correct lines remain
    lines = sample_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "Line 2" in lines
    assert "Line 4" in lines
