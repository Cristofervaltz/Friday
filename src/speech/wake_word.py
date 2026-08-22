"""Wake Word Detector subsystem using Vosk and sounddevice."""

import json
import queue
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import sounddevice as sd  # type: ignore
from vosk import KaldiRecognizer, Model  # type: ignore

from src.utils.safe_print import safe_print


class WakeWordDetector:
    """Listens continuously in the background for a wake word using Vosk."""

    def __init__(
        self,
        model_path_ru: str = "assets/models/vosk-model-ru",
        model_path_en: str = "assets/models/vosk-model-small-en-us-0.15",
    ):
        self.wake_words_ru = ["пятница", "эй пятница"]
        self.wake_words_en = ["friday", "hey friday"]
        self.model_path_ru = model_path_ru
        self.model_path_en = model_path_en
        self.running = False
        self._running = False
        self.thread: threading.Thread | None = None
        self.q: queue.Queue[bytes] = queue.Queue()
        self._callback: Callable[[], None] | None = None
        self._last_triggered: float = 0.0
        self._cooldown: float = 3.0  # seconds between triggers

    def _callback_sd(
        self, indata: Any, frames: int, time_info: Any, status: Any
    ) -> None:
        """This is called (from a sounddevice thread) for each audio block."""
        self.q.put(bytes(indata))

    def _listen_loop(self) -> None:
        try:

            def get_base_path() -> Path:
                if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                    return Path(sys._MEIPASS)
                return Path(__file__).resolve().parent.parent.parent

            model_dir_ru = get_base_path() / self.model_path_ru
            model_dir_en = get_base_path() / self.model_path_en

            if not model_dir_ru.exists() or not model_dir_en.exists():
                safe_print(
                    f"Wake word models not found. RU: {model_dir_ru.exists()}, EN: {model_dir_en.exists()}"
                )
                self.running = False
                self._running = False
                return

            model_ru = Model(str(model_dir_ru))
            model_en = Model(str(model_dir_en))

            samplerate = 16000

            def build_grammar(words: list[str]) -> str:
                words_set = set()
                for phrase in words:
                    for word in phrase.split():
                        words_set.add(word)
                return json.dumps(list(words_set) + ["[unk]"], ensure_ascii=False)

            grammar_ru = build_grammar(self.wake_words_ru)
            grammar_en = build_grammar(self.wake_words_en)

            recognizer_ru = KaldiRecognizer(model_ru, samplerate, grammar_ru)
            recognizer_en = KaldiRecognizer(model_en, samplerate, grammar_en)

            try:
                devices = sd.query_devices()
                device_iter = devices if not isinstance(devices, dict) else [devices]
                has_input = any(d.get("max_input_channels", 0) > 0 for d in device_iter)
                if not has_input:
                    safe_print("No microphone found. Wake word detection disabled.")
                    self.running = False
                    self._running = False
                    return
            except Exception as e:
                safe_print(
                    f"Could not query audio devices ({e}). Wake word detection disabled."
                )
                self.running = False
                self._running = False
                return

            def handle_detection(
                text: str,
                words: list[str],
                recognizer: KaldiRecognizer,
            ) -> bool:
                if text in words:
                    now = time.monotonic()
                    if now - self._last_triggered >= self._cooldown:
                        safe_print(f"Wake word detected: {text}")
                        self._last_triggered = now
                        if self._callback:
                            self._callback()
                    recognizer.Reset()
                    with self.q.mutex:
                        self.q.queue.clear()
                    return True
                return False

            while self.running and self._running:
                stream = None
                try:
                    stream = sd.RawInputStream(
                        samplerate=samplerate,
                        blocksize=4000,
                        device=None,
                        dtype="int16",
                        channels=1,
                        callback=self._callback_sd,
                    )
                    with stream:
                        safe_print(
                            f"Listening for wake words at {samplerate}Hz: {self.wake_words_ru + self.wake_words_en}"
                        )
                        while self.running and self._running:
                            try:
                                # timeout allows checking self.running and cleanly exiting within 500ms
                                data = self.q.get(timeout=0.5)
                            except queue.Empty:
                                continue

                            if recognizer_ru.AcceptWaveform(data):
                                result = json.loads(recognizer_ru.Result())
                                text = result.get("text", "").lower().strip()
                                if text:
                                    handle_detection(
                                        text, self.wake_words_ru, recognizer_ru
                                    )
                            else:
                                recognizer_ru.PartialResult()  # Consume but don't trigger

                            if recognizer_en.AcceptWaveform(data):
                                result = json.loads(recognizer_en.Result())
                                text = result.get("text", "").lower().strip()
                                if text:
                                    handle_detection(
                                        text, self.wake_words_en, recognizer_en
                                    )
                            else:
                                recognizer_en.PartialResult()  # Consume but don't trigger

                except Exception as e:
                    safe_print(f"WakeWordDetector stream error: {e}")
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass
                    if self.running and self._running:
                        safe_print(
                            "Attempting to restart wake word stream in 2 seconds..."
                        )
                        time.sleep(2)
                    else:
                        break

        except Exception as e:
            safe_print(f"WakeWordDetector error: {e}")
        finally:
            self.running = False
            self._running = False
            with self.q.mutex:
                self.q.queue.clear()

    def start(self, callback: Any) -> None:
        """Start the wake word detector background thread."""
        if self.running or self._running:
            return
        self.running = True
        self._running = True
        self._callback = callback
        with self.q.mutex:
            self.q.queue.clear()
        self.thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="WakeWordDetectorThread"
        )
        self.thread.start()

    def stop(self) -> None:
        """Stop wake word listener thread and clear audio queue."""
        self.running = False
        self._running = False
        if self.thread and self.thread.is_alive():
            # Since q.get times out at 500ms, join(timeout=1.0) guarantees clean termination
            self.thread.join(timeout=1.0)
        self.thread = None
        with self.q.mutex:
            self.q.queue.clear()
