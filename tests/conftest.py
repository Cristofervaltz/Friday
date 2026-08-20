import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't read from or write to the global user ~/.friday dir.

    Also strictly suppresses TTS playback across all test execution to guarantee
    no audio output is emitted during testing.
    """
    friday_home = tmp_path / ".friday"
    friday_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRIDAY_HOME", str(friday_home))

    # Initialize settings with TTS disabled
    settings_file = friday_home / "settings.json"
    if not settings_file.exists():
        settings_file.write_text(json.dumps({"tts_enabled": "false"}), encoding="utf-8")

    # nuke ambient env vars so tests dont pollute each other
    for k in list(os.environ.keys()):
        if k.startswith("FRIDAY_") and k != "FRIDAY_HOME":
            monkeypatch.delenv(k, raising=False)

    # Strictly suppress and mock TTS execution to guarantee no audio playback
    try:
        from src.speech import tts_provider

        monkeypatch.setattr(tts_provider.EdgeTTSProvider, "speak", MagicMock())
        monkeypatch.setattr(tts_provider.EdgeTTSProvider, "speak_async", MagicMock())
    except ImportError:
        pass
