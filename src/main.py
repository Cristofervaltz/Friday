"""Application entry point for Friday."""

from __future__ import annotations

import argparse
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

    parser = argparse.ArgumentParser(description="Friday AI Assistant")
    parser.add_argument(
        "--voice-task",
        action="store_true",
        help="Immediately run a voice task and exit",
    )
    parser.add_argument(
        "--task", type=str, help="Immediately run a specific text task and exit"
    )
    args = parser.parse_args()

    app = FridayApplication()
    app.initialize()

    repl = FridayREPL(app)

    if args.voice_task:
        # Run a single voice task
        repl.run_single_voice_task()
        exit_code = 0
    elif args.task:
        # Run a single text task
        repl.run_single_task(args.task)
        exit_code = 0
    else:
        # Start interactive REPL
        exit_code = repl.run()

    app.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
