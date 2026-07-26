import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests don't read from or write to the global user ~/.friday dir."""
    friday_home = tmp_path / ".friday"
    monkeypatch.setenv("FRIDAY_HOME", str(friday_home))
