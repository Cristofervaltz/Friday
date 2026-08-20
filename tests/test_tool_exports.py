"""Tests for verifying tool module exports in src.tools."""

import inspect

import src.tools as tools
from src.tools.base import BaseTool


def test_tool_exports_all_list() -> None:
    # make sure all the required tools are present in __all__
    expected_exports = [
        "BaseTool",
        "ToolResult",
        "ReadFileTool",
        "WriteFileTool",
        "EditFileTool",
        "ListFilesTool",
        "ShellCommandTool",
        "TimeTool",
        "WeatherTool",
        "WebSearchTool",
        "FetchWebPageTool",
        "OpenBrowserTool",
        "WindowManagementTool",
        "ScreenshotTool",
        "SemanticSearchTool",
        "DelegateTaskTool",
    ]

    for export_name in expected_exports:
        assert export_name in tools.__all__, f"{export_name} missing from __all__"
        assert hasattr(tools, export_name), (
            f"{export_name} missing as attr in src.tools"
        )


def test_tool_classes_inherit_from_base_tool() -> None:
    # verify that exported tool classes actually inherit BaseTool
    for name in tools.__all__:
        obj = getattr(tools, name)
        if name in ("BaseTool", "ToolResult"):
            continue
        assert inspect.isclass(obj), f"{name} should be a class"
        assert issubclass(obj, BaseTool), f"{name} must inherit BaseTool"


def test_direct_imports_of_new_tools() -> None:
    # ensure direct imports of the newly exported tools work fine
    from src.tools import DelegateTaskTool, ScreenshotTool, SemanticSearchTool

    assert DelegateTaskTool is not None
    assert ScreenshotTool is not None
    assert SemanticSearchTool is not None
