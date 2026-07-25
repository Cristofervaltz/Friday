"""System tray management for the Friday Daemon."""

import threading
from typing import Callable, Any

try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None  # type: ignore
    Image = None  # type: ignore


def create_default_icon() -> "Image.Image":
    """Create a default generated icon for the tray."""
    # Create a 64x64 blue square with a white 'F'
    img = Image.new("RGB", (64, 64), color=(0, 120, 215))
    draw = ImageDraw.Draw(img)
    # Just draw some basic geometry since we might not have good fonts
    draw.rectangle([16, 16, 48, 24], fill="white")
    draw.rectangle([16, 16, 24, 48], fill="white")
    draw.rectangle([16, 32, 40, 40], fill="white")
    return img


class TrayManager:
    """Manages the system tray icon for the background daemon."""

    def __init__(self, on_exit: Callable[[], None]) -> None:
        """Initialize the tray manager.

        Args:
            on_exit: Callback to execute when the user clicks 'Exit'.
        """
        self._on_exit_callback = on_exit
        self._icon: Any = None

    def _setup_menu(self) -> "pystray.Menu":
        """Create the context menu for the tray icon."""
        return pystray.Menu(
            pystray.MenuItem("Friday Daemon Running", lambda: None, enabled=False),
            pystray.MenuSeparator(),
            pystray.MenuItem("Exit", self._on_menu_exit),
        )

    def _on_menu_exit(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        """Handler for the Exit menu item."""
        self._on_exit_callback()

    def start(self) -> None:
        """Start the system tray icon. Blocks until the icon is stopped."""
        if pystray is None or Image is None:
            print("Warning: pystray or Pillow not installed. Tray disabled.")
            return

        print("Starting system tray icon...")
        image = create_default_icon()
        self._icon = pystray.Icon(
            "friday_daemon", image, "Friday AI Assistant", menu=self._setup_menu()
        )

        # pystray.Icon.run() is blocking and must be called from the main thread
        # in some OSes, but we can usually run it in the main thread of the daemon
        self._icon.run()

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None
