"""Google Speech Recognition provider implementation."""

import logging

from .base import BaseSpeechProvider

try:
    import speech_recognition as sr  # type: ignore

    _SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    _SPEECH_RECOGNITION_AVAILABLE = False


logger = logging.getLogger("friday.speech")


class GoogleSpeechProvider(BaseSpeechProvider):
    """Speech-to-text provider using Google's free Web Speech API.

    Requires internet connection. Does not require an API key.
    """

    def __init__(self, language: str = "ru-RU") -> None:
        """Initialize the Google Speech provider.

        Args:
            language: BCP-47 language tag for recognition (e.g. 'en-US', 'ru-RU').
        """
        if not _SPEECH_RECOGNITION_AVAILABLE:
            raise RuntimeError(
                "speech_recognition library is not installed. "
                "Please run: pip install .[speech]"
            )

        self.language = language
        self.recognizer = sr.Recognizer()

    def listen_and_transcribe(
        self, timeout: int = 10, phrase_time_limit: int = 15
    ) -> str:
        """Listen to default microphone and transcribe using Google STT."""
        try:
            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

                logger.info(f"Listening for speech (timeout={timeout}s)...")
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

                logger.info("Speech captured. Transcribing...")

        except sr.WaitTimeoutError:
            raise TimeoutError(
                "No speech detected within the timeout period."
            ) from None
        except OSError as exc:
            raise RuntimeError(f"Microphone unavailable: {exc}") from exc

        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            return str(text)
        except sr.UnknownValueError:
            raise ValueError(
                "Google Speech Recognition could not understand audio"
            ) from None
        except sr.RequestError as exc:
            raise RuntimeError(
                f"Could not request results from Google API; {exc}"
            ) from exc
