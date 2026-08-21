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
        self, timeout: int = 10, phrase_time_limit: int = 15, abort_event=None
    ) -> str:
        """Listen to default microphone and transcribe using Google STT."""
        import threading

        try:
            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

                logger.info(f"Listening for speech (timeout={timeout}s)...")

                result_container = {}

                def listen_worker():
                    try:
                        audio = self.recognizer.listen(
                            source, timeout=timeout, phrase_time_limit=phrase_time_limit
                        )
                        result_container["audio"] = audio
                    except Exception as e:
                        result_container["error"] = e

                worker_thread = threading.Thread(target=listen_worker)
                worker_thread.daemon = True
                worker_thread.start()

                while worker_thread.is_alive():
                    if abort_event and abort_event.is_set():
                        # Try to force close the stream to unblock the worker thread
                        if hasattr(source, "stream") and source.stream is not None:
                            try:
                                source.stream.close()
                            except Exception:
                                pass
                        raise InterruptedError("Voice recording aborted by user.")
                    worker_thread.join(timeout=0.1)

                if "error" in result_container:
                    raise result_container["error"]

                audio = result_container.get("audio")
                if not audio:
                    raise RuntimeError("Failed to capture audio.")

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
