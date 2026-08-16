"""Port discovery and runtime port file utilities for Friday."""

from __future__ import annotations

import socket
from pathlib import Path

_DEFAULT_PORT = 8000
_PORT_RANGE_SIZE = 100  # Try ports 8000–8099
_RUNTIME_PORT_FILENAME = "runtime_port"


def find_free_port(start: int = _DEFAULT_PORT, range_size: int = _PORT_RANGE_SIZE) -> int:
    """Find the first available TCP port starting from *start*.

    Tries each port in [start, start + range_size) by attempting to bind.
    Returns the first port that is free.

    Raises:
        RuntimeError: If no free port is found in the range.
    """
    for port in range(start, start + range_size):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue

    raise RuntimeError(
        f"No free port found in range {start}–{start + range_size - 1}. "
        "Close some applications and try again."
    )


def write_runtime_port(port: int, app_home: Path | None = None) -> Path:
    """Write the chosen port to ``~/.friday/runtime_port`` so other components can find it.

    Returns the path to the written file.
    """
    home = app_home or (Path.home() / ".friday")
    home.mkdir(parents=True, exist_ok=True)
    port_file = home / _RUNTIME_PORT_FILENAME
    port_file.write_text(str(port), encoding="utf-8")
    return port_file


def read_runtime_port(app_home: Path | None = None) -> int:
    """Read the port from ``~/.friday/runtime_port``.

    Returns the port number, or the default (8000) if the file is missing/corrupt.
    """
    home = app_home or (Path.home() / ".friday")
    port_file = home / _RUNTIME_PORT_FILENAME
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError, OSError):
        return _DEFAULT_PORT


def cleanup_runtime_port(app_home: Path | None = None) -> None:
    """Remove the runtime port file on shutdown."""
    home = app_home or (Path.home() / ".friday")
    port_file = home / _RUNTIME_PORT_FILENAME
    try:
        port_file.unlink(missing_ok=True)
    except OSError:
        pass
