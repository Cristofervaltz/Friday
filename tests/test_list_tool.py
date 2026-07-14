"""Tests for ListFilesTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tools import ListFilesTool


@pytest.fixture
def list_tool() -> ListFilesTool:
    """Create ListFilesTool instance."""
    return ListFilesTool()


@pytest.fixture
def sample_directory(tmp_path: Path) -> Path:
    """Create a sample directory structure for testing."""
    # Create files
    (tmp_path / "file1.txt").write_text("content 1")
    (tmp_path / "file2.py").write_text("print('hello')")
    (tmp_path / "file3.md").write_text("# Readme")

    # Create subdirectory with files
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested1.txt").write_text("nested content")
    (subdir / "nested2.py").write_text("print('nested')")

    # Create hidden file
    (tmp_path / ".hidden").write_text("hidden content")

    return tmp_path


def test_list_tool_has_correct_name(list_tool: ListFilesTool) -> None:
    """Test that ListFilesTool has the correct name."""
    assert list_tool.name == "list_files"


def test_list_tool_has_description(list_tool: ListFilesTool) -> None:
    """Test that ListFilesTool has a description."""
    assert len(list_tool.description) > 0
    assert "list" in list_tool.description.lower()


def test_list_tool_has_parameters_schema(list_tool: ListFilesTool) -> None:
    """Test that ListFilesTool has a parameters schema."""
    schema = list_tool.parameters_schema
    assert schema["type"] == "object"
    assert "path" in schema["properties"]
    assert "pattern" in schema["properties"]


def test_list_files_basic(list_tool: ListFilesTool, sample_directory: Path) -> None:
    """Test basic directory listing."""
    result = list_tool.execute(path=str(sample_directory))

    assert result.success
    assert "file1.txt" in result.output
    assert "file2.py" in result.output
    assert "file3.md" in result.output


def test_list_files_with_pattern(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test listing with glob pattern."""
    result = list_tool.execute(path=str(sample_directory), pattern="*.py")

    assert result.success
    assert "file2.py" in result.output
    assert "file1.txt" not in result.output


def test_list_files_recursive(list_tool: ListFilesTool, sample_directory: Path) -> None:
    """Test recursive directory listing."""
    result = list_tool.execute(path=str(sample_directory), recursive=True)

    assert result.success
    assert "nested1.txt" in result.output
    assert "nested2.py" in result.output


def test_list_files_with_hidden(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test listing with hidden files."""
    result = list_tool.execute(path=str(sample_directory), show_hidden=True)

    assert result.success
    assert ".hidden" in result.output


def test_list_files_without_hidden(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test listing without hidden files (default)."""
    result = list_tool.execute(path=str(sample_directory), show_hidden=False)

    assert result.success
    assert ".hidden" not in result.output


def test_list_files_with_details(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test listing with file details."""
    result = list_tool.execute(path=str(sample_directory), show_details=True)

    assert result.success
    # Should show size info
    assert "B" in result.output or "KB" in result.output


def test_list_files_sort_by_name(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test sorting by name."""
    result = list_tool.execute(path=str(sample_directory), sort_by="name")

    assert result.success
    # Check that files appear in order
    idx1 = result.output.index("file1.txt")
    idx2 = result.output.index("file2.py")
    idx3 = result.output.index("file3.md")
    assert idx1 < idx2 < idx3


def test_list_files_sort_by_size(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test sorting by size."""
    # Create files with different sizes
    (sample_directory / "large.txt").write_text("x" * 1000)
    (sample_directory / "small.txt").write_text("x")

    result = list_tool.execute(path=str(sample_directory), sort_by="size")

    assert result.success
    # Larger file should appear first
    idx_large = result.output.index("large.txt")
    idx_small = result.output.index("small.txt")
    assert idx_large < idx_small


def test_list_files_directory_not_found(
    list_tool: ListFilesTool, tmp_path: Path
) -> None:
    """Test error handling for non-existent directory."""
    result = list_tool.execute(path=str(tmp_path / "nonexistent"))

    assert not result.success
    assert "not found" in result.error.lower()


def test_list_files_path_not_directory(
    list_tool: ListFilesTool, tmp_path: Path
) -> None:
    """Test error handling for non-directory path."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")

    result = list_tool.execute(path=str(file_path))

    assert not result.success
    assert "not a directory" in result.error.lower()


def test_list_files_empty_directory(list_tool: ListFilesTool, tmp_path: Path) -> None:
    """Test listing an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = list_tool.execute(path=str(empty_dir))

    assert result.success
    assert "(empty)" in result.output


def test_list_files_default_current_directory(list_tool: ListFilesTool) -> None:
    """Test listing with default path (current directory)."""
    result = list_tool.execute()

    assert result.success
    # Should list something from current directory


def test_list_files_too_many_entries(tmp_path: Path) -> None:
    """Test error handling for too many entries."""
    tool = ListFilesTool(max_entries=5)  # Very small limit

    # Create many files
    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text(f"content {i}")

    result = tool.execute(path=str(tmp_path))

    assert not result.success
    assert "too many" in result.error.lower()


def test_list_files_recursive_with_pattern(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test recursive listing with pattern."""
    result = list_tool.execute(
        path=str(sample_directory), pattern="*.py", recursive=True
    )

    assert result.success
    assert "file2.py" in result.output
    assert "nested2.py" in result.output
    assert "file1.txt" not in result.output


def test_list_files_shows_directory_icon(
    list_tool: ListFilesTool, sample_directory: Path
) -> None:
    """Test that directories are shown with appropriate icon."""
    result = list_tool.execute(path=str(sample_directory))

    assert result.success
    # Should show folder icon for subdirectory
    assert "subdir" in result.output
