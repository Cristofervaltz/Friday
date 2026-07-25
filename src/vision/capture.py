"""Screen capture utilities using mss and Pillow."""

from __future__ import annotations

import base64
import io
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

try:
    import mss
    from PIL import Image

    _VISION_AVAILABLE = True
except ImportError:
    _VISION_AVAILABLE = False

logger = logging.getLogger("friday.vision")


class ScreenCapture:
    """Utility for capturing screen contents."""

    def __init__(self) -> None:
        """Initialize screen capture."""
        if not _VISION_AVAILABLE:
            raise RuntimeError(
                "Vision dependencies not installed. Run: pip install .[vision]"
            )

    def grab_screenshot(self, monitor_index: int = 1) -> PILImage:
        """Capture a screenshot of a specific monitor.

        Args:
            monitor_index: The index of the monitor to capture (1-indexed).
                0 means all monitors.

        Returns:
            A PIL Image containing the screenshot.
        """
        with mss.mss() as sct:
            if monitor_index < 0 or monitor_index >= len(sct.monitors):
                logger.warning(
                    f"Invalid monitor index {monitor_index}. Falling back to 1."
                )
                monitor_index = 1

            monitor = sct.monitors[monitor_index]
            logger.info(f"Capturing screenshot of monitor {monitor_index}: {monitor}")

            # Grab the data
            sct_img = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img

    def get_base64_screenshot(
        self, monitor_index: int = 1, max_size: tuple[int, int] | None = (1920, 1080)
    ) -> str:
        """Capture a screenshot and return it as a base64 encoded JPEG string.

        Args:
            monitor_index: The index of the monitor.
            max_size: Optional maximum dimensions to resize the image to,
                preserving aspect ratio.

        Returns:
            Base64 encoded JPEG string.
        """
        img = self.grab_screenshot(monitor_index)

        if max_size:
            # Thumbnail preserves aspect ratio and modifies in-place
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        # Save as JPEG for smaller payload size
        img.save(buffer, format="JPEG", quality=85)

        return base64.b64encode(buffer.getvalue()).decode("utf-8")
