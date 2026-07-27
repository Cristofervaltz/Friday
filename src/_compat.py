"""Compatibility helpers for internal cross-module imports."""

from __future__ import annotations

from typing import Any


def load_settings_safe() -> dict[str, Any]:
    """Load settings from config.json without circular imports."""
    import json
    from pathlib import Path

    app_home = Path.home() / ".friday"
    config_file = app_home / "config.json"
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return {}
    return {}
