"""Vision tools for Friday."""

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.vision.capture import ScreenCapture


class ScreenshotTool(BaseTool):
    """Tool to capture a screenshot of the user's screen."""

    @property
    def name(self) -> str:
        return "take_screenshot"

    @property
    def description(self) -> str:
        return (
            "Take a screenshot of the user's screen. Returns a base64 encoded "
            "JPEG image. Use this when you need to see what is on the screen "
            "(e.g., to read error messages, check UI layout, or verify state)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "monitor": {
                    "type": "integer",
                    "description": "Monitor index to capture (default: 1)",
                }
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Capture a screenshot and return as base64."""
        try:
            capture = ScreenCapture()
            monitor_idx = int(kwargs.get("monitor", 1))

            # Get base64 string
            b64_image = capture.get_base64_screenshot(monitor_index=monitor_idx)

            # Return as output
            return ToolResult(
                success=True, output=f"data:image/jpeg;base64,{b64_image}"
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Screenshot failed: {e}")
