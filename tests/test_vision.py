"""Tests for the vision subsystem."""

from unittest.mock import MagicMock, patch

from src.tools.vision_tool import ScreenshotTool


@patch("src.tools.vision_tool.ScreenCapture")
def test_vision_tool_success(mock_capture_class: MagicMock) -> None:
    """Test successful screenshot capture."""
    mock_capture = MagicMock()
    mock_capture.get_base64_screenshot.return_value = "dummy_base64"
    mock_capture_class.return_value = mock_capture

    tool = ScreenshotTool()
    assert tool.name == "take_screenshot"
    assert tool.description

    result = tool.execute(monitor=1)

    assert result.success is True
    assert result.output == "data:image/jpeg;base64,dummy_base64"
    mock_capture.get_base64_screenshot.assert_called_once_with(monitor_index=1)


@patch("src.tools.vision_tool.ScreenCapture")
def test_vision_tool_failure(mock_capture_class: MagicMock) -> None:
    """Test screenshot capture failure."""
    mock_capture_class.side_effect = RuntimeError("Vision deps missing")

    tool = ScreenshotTool()
    result = tool.execute()

    assert result.success is False
    assert "Screenshot failed: Vision deps missing" in str(result.error)
