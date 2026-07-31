import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

import sounddevice as sd  # type: ignore
from vosk import KaldiRecognizer, Model  # type: ignore


class WakeWordDetector:
    """Listens continuously in the background for a wake word using Vosk."""

    def __init__(
        self,
        model_path: str = "assets/models/vosk-model-ru",
        wake_words: list[str] | None = None,
    ):
        if wake_words is None:
            wake_words = ["friday", "hey friday", "пятница", "эй пятница"]
        self.wake_words = [w.lower() for w in wake_words]
        self.model_path = model_path
        self.running = False
        self.thread: threading.Thread | None = None
        self.q: queue.Queue[bytes] = queue.Queue()
        self._callback = None
        self._last_triggered: float = 0.0
        self._cooldown: float = 2.0  # seconds between triggers

    def _callback_sd(
        self, indata: Any, frames: int, time_info: Any, status: Any
    ) -> None:
        """This is called (from a separate thread) for each audio block."""
        # Removed print(status, file=sys.stderr) which causes OSError
        # on Windows GUI apps
        self.q.put(bytes(indata))

    def _listen_loop(self) -> None:
        try:

            def get_base_path() -> Path:
                if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                    return Path(sys._MEIPASS)
                return Path(__file__).resolve().parent.parent.parent

            model_dir = get_base_path() / self.model_path
            if not model_dir.exists():
                print(f"Wake word model not found at: {model_dir}")
                return

            model = Model(str(model_dir))
            samplerate = 16000
            recognizer = KaldiRecognizer(model, samplerate)

            with sd.RawInputStream(
                samplerate=samplerate,
                blocksize=8000,
                device=None,
                dtype="int16",
                channels=1,
                callback=self._callback_sd,
            ):
                print(f"Listening for wake words: {self.wake_words}")
                while self.running:
                    data = self.q.get()
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").lower()
                        if text:
                            print(f"Heard: {text}")
                            for w in self.wake_words:
                                if w in text:
                                    now = time.monotonic()
                                    if now - self._last_triggered >= self._cooldown:
                                        print(f"WAKE WORD DETECTED: {w}")
                                        self._last_triggered = now
                                        if self._callback:
                                            self._callback()
                                    break
                    else:
                        partial = json.loads(recognizer.PartialResult())
                        text = partial.get("partial", "").lower()
                        for w in self.wake_words:
                            if w in text:
                                now = time.monotonic()
                                if now - self._last_triggered >= self._cooldown:
                                    print(f"WAKE WORD DETECTED (partial): {w}")
                                    self._last_triggered = now
                                    if self._callback:
                                        self._callback()
                                # always reset recognizer on partial match
                                # to avoid re-detection
                                recognizer.Reset()
                                break
        except Exception as e:
            print(f"WakeWordDetector error: {e}")

    def start(self, callback: Any) -> None:
        if self.running:
            return
        self.running = True
        self._callback = callback
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        if self.thread:
            self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
