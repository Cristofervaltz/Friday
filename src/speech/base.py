"""Base interfaces for Friday's Speech Recognition subsystem."""

from abc import ABC, abstractmethod


class BaseSpeechProvider(ABC):
    """Abstract interface for speech-to-text providers."""

    @abstractmethod
    def listen_and_transcribe(
        self, timeout: int = 10, phrase_time_limit: int = 15
    ) -> str:
        """Listen to microphone input and return transcribed text.

        Args:
            timeout: Max seconds to wait for speech to begin.
            phrase_time_limit: Max seconds a continuous phrase can last.

        Returns:
            The transcribed text.

        Raises:
            RuntimeError: If microphone is unavailable.
            TimeoutError: If no speech is detected within timeout.
            ValueError: If speech is incomprehensible or transcription fails.
        """
