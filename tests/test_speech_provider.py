import threading
from unittest.mock import MagicMock, patch

import pytest

from src.speech.google_provider import GoogleSpeechProvider


def test_google_provider_successful_transcription() -> None:
    """Verify that GoogleSpeechProvider correctly listens and transcribes via the threaded worker."""
    provider = GoogleSpeechProvider(language="en-US")

    with patch("src.speech.google_provider.sr") as mock_sr:

        class DummyWaitTimeoutError(Exception):
            pass

        class DummyUnknownValueError(Exception):
            pass

        mock_sr.WaitTimeoutError = DummyWaitTimeoutError
        mock_sr.UnknownValueError = DummyUnknownValueError

        # Mock Microphone context manager
        mock_mic = MagicMock()
        mock_sr.Microphone.return_value.__enter__.return_value = mock_mic

        # Mock the listen function to return fake audio
        fake_audio = MagicMock()
        mock_sr.Recognizer.return_value.listen.return_value = fake_audio

        # Mock the transcription result
        mock_sr.Recognizer.return_value.recognize_google.return_value = "hello world"

        # We need to ensure the class uses the mocked recognizer.
        # But wait, __init__ was called before patch! We must patch before init or set it explicitly.
        provider.recognizer = mock_sr.Recognizer()

        result = provider.listen_and_transcribe(timeout=2, phrase_time_limit=3)
        assert result == "hello world"
        provider.recognizer.listen.assert_called_once()
        provider.recognizer.recognize_google.assert_called_once_with(
            fake_audio, language="en-US"
        )


def test_google_provider_abort_closes_stream() -> None:
    """Verify that if abort_event is set, the PyAudio stream is forced closed and InterruptedError is raised."""
    provider = GoogleSpeechProvider(language="en-US")
    abort_event = threading.Event()

    with patch("src.speech.google_provider.sr") as mock_sr:

        class DummyWaitTimeoutError(Exception):
            pass

        class DummyUnknownValueError(Exception):
            pass

        mock_sr.WaitTimeoutError = DummyWaitTimeoutError
        mock_sr.UnknownValueError = DummyUnknownValueError

        # Mock Microphone
        mock_mic = MagicMock()
        mock_stream = MagicMock()
        mock_mic.stream = mock_stream
        mock_sr.Microphone.return_value.__enter__.return_value = mock_mic

        provider.recognizer = mock_sr.Recognizer()

        # Make the listen function block forever (or long enough) to trigger the abort loop
        def blocking_listen(*args: object, **kwargs: object) -> object:
            abort_event.set()  # trigger abort during listening
            import time

            time.sleep(1)  # simulate blocking
            return MagicMock()

        provider.recognizer.listen.side_effect = blocking_listen

        with pytest.raises(RuntimeError, match="Voice recording aborted by user"):
            provider.listen_and_transcribe(
                timeout=5, phrase_time_limit=5, abort_event=abort_event
            )

        # Verify stream.stop_stream() was called to unblock PyAudio
        mock_stream.stop_stream.assert_called_once()
