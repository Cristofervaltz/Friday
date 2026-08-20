import json
import queue
import sys
import threading
import time
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
        self.thread: threading.Thread | None = None
        self.q: queue.Queue[bytes] = queue.Queue()
        self._callback = None
        self._last_triggered: float = 0.0
        self._cooldown: float = 2.0  # seconds between triggers

    def _callback_sd(
        self, indata: Any, frames: int, time_info: Any, status: Any
    ) -> None:
        """This is called (from a separate thread) for each audio block."""
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
                has_input = any(
                    d.get("max_input_channels", 0) > 0
                    for d in device_iter
                )
                if not has_input:
                    safe_print("No microphone found. Wake word detection disabled.")
                    return
            except Exception as e:
                safe_print(
                    f"Could not query audio devices ({e}). Wake word detection disabled."
                )
                return

            try:
                stream = sd.RawInputStream(
                    samplerate=samplerate,
                    blocksize=8000,
                    device=None,
                    dtype="int16",
                    channels=1,
                    callback=self._callback_sd,
                )
            except Exception as audio_err:
                safe_print(
                    f"Could not open microphone: {audio_err}. Wake word detection disabled."
                )
                return

            with stream:
                safe_print(
                    f"Listening for wake words at {samplerate}Hz: {self.wake_words_ru + self.wake_words_en}"
                )
                while self.running:
                    data = self.q.get()

                    def handle_detection(
                        text: str,
                        words: list[str],
                        recognizer: KaldiRecognizer,
                        is_partial: bool,
                    ) -> bool:
                        for w in words:
                            if w in text:
                                now = time.monotonic()
                                if now - self._last_triggered >= self._cooldown:
                                    prefix = (
                                        "(partial)" if is_partial else "full result"
                                    )
                                    safe_print(
                                        f"Wake word detected in {prefix}: {text}"
                                    )
                                    self._last_triggered = now
                                    if self._callback:
                                        self._callback()
                                recognizer.Reset()
                                with self.q.mutex:
                                    self.q.queue.clear()
                                return True
                        return False

                    if recognizer_ru.AcceptWaveform(data):
                        result = json.loads(recognizer_ru.Result())
                        text = result.get("text", "").lower()
                        if text:
                            handle_detection(
                                text, self.wake_words_ru, recognizer_ru, False
                            )
                    else:
                        partial = json.loads(recognizer_ru.PartialResult())
                        text = partial.get("partial", "").lower()
                        if text:
                            if handle_detection(
                                text, self.wake_words_ru, recognizer_ru, True
                            ):
                                recognizer_en.Reset()
                                continue

                    if recognizer_en.AcceptWaveform(data):
                        result = json.loads(recognizer_en.Result())
                        text = result.get("text", "").lower()
                        if text:
                            handle_detection(
                                text, self.wake_words_en, recognizer_en, False
                            )
                    else:
                        partial = json.loads(recognizer_en.PartialResult())
                        text = partial.get("partial", "").lower()
                        if text:
                            if handle_detection(
                                text, self.wake_words_en, recognizer_en, True
                            ):
                                recognizer_ru.Reset()

        except Exception as e:
            safe_print(f"WakeWordDetector error: {e}")

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
