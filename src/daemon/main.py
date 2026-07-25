"""Main entry point for the Friday Background Daemon."""

import sys
import threading
import time

from .events import EventMonitor
from .hotkeys import HotkeyManager
from .tray import TrayManager


class FridayDaemon:
    """The main daemon controller."""

    def __init__(self) -> None:
        """Initialize the daemon components."""
        self.hotkeys = HotkeyManager()
        self.events = EventMonitor()
        self.tray = TrayManager(on_exit=self.stop)
        self._running = False

    def start(self) -> None:
        """Start the daemon."""
        print("Starting Friday Daemon...")
        self._running = True

        # Start background listeners
        self.hotkeys.start()
        self.events.start()

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
