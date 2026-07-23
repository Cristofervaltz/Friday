"""Tests for the speech recognition subsystem."""

from unittest.mock import MagicMock, patch

import pytest

# We need to mock the speech_recognition import for tests
# because CI environments might not have PyAudio installed or audio devices
import speech_recognition as sr  # type: ignore

from src.speech.base import BaseSpeechProvider
from src.speech.google_provider import GoogleSpeechProvider


class MockSpeechProvider(BaseSpeechProvider):
    """A dummy provider for testing the base interface."""

    def listen_and_transcribe(
        self, timeout: int = 10, phrase_time_limit: int = 15
    ) -> str:
        return "mock transcription"


def test_base_provider_interface() -> None:
    """Test that the base provider interface can be implemented."""
    provider = MockSpeechProvider()
    assert provider.listen_and_transcribe() == "mock transcription"


@patch("src.speech.google_provider.sr.Microphone")
@patch("src.speech.google_provider.sr.Recognizer")
def test_google_provider_successful_transcription(
    mock_recognizer_cls: MagicMock, mock_microphone_cls: MagicMock
) -> None:
    """Test that Google provider successfully returns transcribed text."""
    mock_recognizer = MagicMock()
    mock_recognizer_cls.return_value = mock_recognizer

    mock_audio = MagicMock()
    mock_recognizer.listen.return_value = mock_audio
    mock_recognizer.recognize_google.return_value = "hello world"

    mock_source = MagicMock()
    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = mock_source
    mock_microphone_cls.return_value = mock_mic

    provider = GoogleSpeechProvider()
    result = provider.listen_and_transcribe(timeout=5)

    assert result == "hello world"
    mock_recognizer.adjust_for_ambient_noise.assert_called_once_with(
        mock_source, duration=1.0
    )
    mock_recognizer.listen.assert_called_once_with(
        mock_source, timeout=5, phrase_time_limit=15
    )
    mock_recognizer.recognize_google.assert_called_once_with(
        mock_audio, language="ru-RU"
    )


@patch("src.speech.google_provider.sr.Microphone")
@patch("src.speech.google_provider.sr.Recognizer")
def test_google_provider_timeout(
    mock_recognizer_cls: MagicMock, mock_microphone_cls: MagicMock
) -> None:
    """Test that Google provider raises TimeoutError when no speech is detected."""
    mock_recognizer = MagicMock()
    mock_recognizer_cls.return_value = mock_recognizer
    mock_recognizer.listen.side_effect = sr.WaitTimeoutError

    mock_source = MagicMock()
    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = mock_source
    mock_microphone_cls.return_value = mock_mic

    provider = GoogleSpeechProvider()

    with pytest.raises(TimeoutError, match="No speech detected"):
        provider.listen_and_transcribe()


@patch("src.speech.google_provider.sr.Microphone")
@patch("src.speech.google_provider.sr.Recognizer")
def test_google_provider_unknown_value(
    mock_recognizer_cls: MagicMock, mock_microphone_cls: MagicMock
) -> None:
    """Test that Google provider raises ValueError when speech is incomprehensible."""
    mock_recognizer = MagicMock()
    mock_recognizer_cls.return_value = mock_recognizer
    mock_recognizer.recognize_google.side_effect = sr.UnknownValueError

    mock_source = MagicMock()
    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = mock_source
    mock_microphone_cls.return_value = mock_mic

    provider = GoogleSpeechProvider()

    with pytest.raises(ValueError, match="could not understand audio"):
        provider.listen_and_transcribe()


@patch("src.speech.google_provider._SPEECH_RECOGNITION_AVAILABLE", False)
def test_google_provider_missing_dependencies() -> None:
    """Test that Google provider raises RuntimeError when dependencies are missing."""
    with pytest.raises(
        RuntimeError, match="speech_recognition library is not installed"
    ):
        GoogleSpeechProvider()
