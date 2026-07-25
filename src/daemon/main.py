"""Main entry point for the Friday Background Daemon."""

import sys
import time

from .events import EventMonitor
from .hotkeys import HotkeyManager
from .tray import TrayManager

try:
    from ..api.server import start_server
except ImportError:
    start_server = None  # type: ignore


class FridayDaemon:
    """The main daemon controller."""

    def __init__(self) -> None:
        """Initialize the daemon components."""
        self.hotkeys = HotkeyManager()
        self.events = EventMonitor()
        self.tray = TrayManager(on_exit=self.stop)
        self._running = False

    def start(self) -> None:
        """Start the daemon loops."""
        print("Starting Friday Daemon...")
        self._running = True
        # Start background listeners
        self.hotkeys.start()
        self.events.start()

        # Start API server in background
        if start_server is not None:
            print("Starting local API server...")
            import threading

            threading.Thread(target=start_server, daemon=True).start()
        else:
            print("Warning: API server could not be imported. GUI will be unavailable.")

        # Start tray icon (this blocks on most OSes)
        self.tray.start()

        # If tray.start() didn't block (e.g., if pystray is missing),
        # we need to keep the main thread alive manually
        if self._running:
            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()

    def stop(self) -> None:
        """Stop all daemon components."""
        if not self._running:
            return

        print("Stopping Friday Daemon...")
        self._running = False
        self.hotkeys.stop()
        self.events.stop()
        self.tray.stop()
        print("Daemon stopped.")
        # Force exit just in case threads hang
        sys.exit(0)


def main() -> int:
    """Daemon entry point."""
    daemon = FridayDaemon()
    daemon.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
