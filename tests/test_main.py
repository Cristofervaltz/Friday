"""Tests for Friday application entry point."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.main import main


def test_main_returns_zero_on_success(tmp_path: Path) -> None:
    """Test that main() returns 0 on successful execution."""
    with patch("src.main.FridayApplication") as mock_app_class:
        mock_app = MagicMock()
        mock_app.run.return_value = 0
        mock_app_class.return_value = mock_app

        exit_code = main()

        assert exit_code == 0
        mock_app.initialize.assert_called_once()
        mock_app.run.assert_called_once()


def test_main_initializes_application(tmp_path: Path) -> None:
    """Test that main() properly initializes the application."""
    with patch("src.main.FridayApplication") as mock_app_class:
        mock_app = MagicMock()
        mock_app.run.return_value = 0
        mock_app_class.return_value = mock_app

        main()

        mock_app_class.assert_called_once()
        mock_app.initialize.assert_called_once()
