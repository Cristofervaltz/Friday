"""Speech Recognition subsystem for voice commands."""

from .base import BaseSpeechProvider
from .google_provider import GoogleSpeechProvider

__all__ = ["BaseSpeechProvider", "GoogleSpeechProvider"]
