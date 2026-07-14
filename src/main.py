"""Application entry point for Friday."""

from __future__ import annotations

from .runtime import FridayApplication


def main() -> int:
    """Initialize and run the Friday application."""
    app = FridayApplication()
    app.initialize()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
