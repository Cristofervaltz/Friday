"""Hotkey management for the Friday Daemon."""

import subprocess
import sys
from typing import Any

try:
    from pynput import keyboard  # type: ignore
except ImportError:
    keyboard = None  # type: ignore


class HotkeyManager:
    """Manages global hotkeys for the background daemon."""

    def __init__(self, combo: str = "<ctrl>+<alt>+<space>"):
        """Initialize the hotkey manager.

        Args:
            combo: The hotkey combination to listen for.
        """
        self.combo = combo
        self._listener: Any = None

    def _on_activate(self) -> None:
        """Callback when the hotkey is pressed."""
        print(f"Hotkey {self.combo} pressed! Spawning Friday...")

        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, "-m", "src.main", "--voice-task"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
                )
            else:
                subprocess.Popen([sys.executable, "-m", "src.main", "--voice-task"])
        except Exception as e:
            print(f"Error launching Friday: {e}")

    def start(self) -> None:
        """Start listening for hotkeys in the background."""
        if keyboard is None:
            print("Warning: pynput not installed. Hotkeys disabled.")
            return

        print(f"Listening for hotkey: {self.combo}")
        self._listener = keyboard.GlobalHotKeys({self.combo: self._on_activate})
        self._listener.start()

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if self._listener:
            self._listener.stop()
            self._listener = None
