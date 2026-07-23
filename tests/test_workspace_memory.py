"""Tests for WorkspaceMemory in src/memory/workspace.py."""

from __future__ import annotations

from pathlib import Path

from src.memory.workspace import WorkspaceMemory


def test_workspace_memory_ops(tmp_path: Path) -> None:
    """Test setting, getting, listing, and deleting keys in workspace memory."""
    filepath = tmp_path / "memory.json"
    memory = WorkspaceMemory(memory_path=filepath)

    assert memory.list_keys() == []
    memory.set("tech_stack", "python")
    memory.set("version", "0.1.0")

    assert memory.get("tech_stack") == "python"
    assert memory.get("missing", "default") == "default"
    assert memory.has("version") is True
    assert set(memory.list_keys()) == {"tech_stack", "version"}

    # Test persistence by reloading
    reloaded = WorkspaceMemory(memory_path=filepath)
    assert reloaded.get("tech_stack") == "python"

    # Test delete
    assert memory.delete("version") is True
    assert memory.has("version") is False
    assert memory.delete("nonexistent") is False


def test_workspace_memory_context_formatting(tmp_path: Path) -> None:
    """Test generating system prompt context string."""
    filepath = tmp_path / "memory.json"
    memory = WorkspaceMemory(memory_path=filepath)

    assert memory.build_system_context() == ""

    memory.set("project", "Friday")
    memory.set("language", "Python")

    context = memory.build_system_context()
    assert "--- Workspace Context Memory ---" in context
    assert "- project: Friday" in context
    assert "- language: Python" in context
