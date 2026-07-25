"""File event monitoring for the Friday Daemon."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore
except ImportError:
    FileSystemEventHandler = object  # type: ignore
    Observer = None


class TriggerHandler(FileSystemEventHandler):  # type: ignore[misc,valid-type]
    """Handles file creation events in the triggers directory."""

    def on_created(self, event: FileSystemEvent) -> None:
        """Called when a file or directory is created."""
        if event.is_directory or not event.src_path.endswith(".txt"):
            return

        self._process_trigger(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Called when a file or directory is modified."""
        if event.is_directory or not event.src_path.endswith(".txt"):
            return

        self._process_trigger(event.src_path)

    def _process_trigger(self, path: str) -> None:
        """Process a trigger file.

        Reads the task from the file, spawns Friday to execute it,
        and then deletes the trigger file.
        """
        # Wait a tiny bit to ensure file is fully written
        time.sleep(0.1)

        try:
            with open(path, "r", encoding="utf-8") as f:
                task = f.read().strip()

            if not task:
                return

            print(f"Trigger received from {path}: {task}")

            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, "-m", "src.main", "--task", task],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
                )
            else:
                subprocess.Popen([sys.executable, "-m", "src.main", "--task", task])

            # Clean up the trigger file
            try:
                os.remove(path)
            except OSError:
                pass

        except Exception as e:
            print(f"Failed to process trigger {path}: {e}")


class EventMonitor:
    """Monitors a specific directory for file-based triggers."""

    def __init__(self) -> None:
        """Initialize the event monitor."""
        self._observer: Any = None

        # Create triggers directory in user home
        home = Path.home()
        self.triggers_dir = home / ".friday" / "triggers"
        self.triggers_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start monitoring for file events."""
        if Observer is None:
            print("Warning: watchdog not installed. Event monitoring disabled.")
            return

        print(f"Monitoring directory for triggers: {self.triggers_dir}")
        self._observer = Observer()
        event_handler = TriggerHandler()
        self._observer.schedule(event_handler, str(self.triggers_dir), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        """Stop monitoring."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
