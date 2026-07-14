"""Application entry point for Friday."""

from __future__ import annotations

import sys

from .cli import FridayREPL
from .runtime import FridayApplication


def main() -> int:
    """Initialize and run the Friday application."""
    # Fix Windows console encoding for emoji/unicode
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        except AttributeError:
            pass
    
    app = FridayApplication()
    app.initialize()
    
    # Start interactive REPL
    repl = FridayREPL(app)
    exit_code = repl.run()
    
    app.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
