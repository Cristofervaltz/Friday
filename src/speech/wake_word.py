import sys
import queue
import threading
import json
from pathlib import Path

class WakeWordDetector:
    """Listens continuously in the background for a wake word using Vosk."""

    def __init__(self, model_path: str = "assets/models/vosk-model-ru", wake_words: list[str] = None):
        self.model_path = model_path
        self.wake_words = wake_words or ["пятница", "эй пятница", "friday", "фрайдей"]
        self.q = queue.Queue()
        self.running = False
        self.thread = None
        self._callback = None

    def _callback_sd(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stderr)
        self.q.put(bytes(indata))

    def _listen_loop(self):
        try:
            # We import here so it doesn't slow down global startup
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer
            import os

            def get_base_path():
                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    return sys._MEIPASS
                return os.path.abspath(".")

            model_dir = Path(get_base_path()) / self.model_path
            if not model_dir.exists():
                print(f"Vosk model not found at {model_dir}. Wake word disabled.")
                return

            model = Model(str(model_dir))
            device_info = sd.query_devices(sd.default.device[0], 'input')
            samplerate = int(device_info['default_samplerate'])
            
            recognizer = KaldiRecognizer(model, samplerate)
            print("WakeWordDetector started listening...")
            
            with sd.RawInputStream(samplerate=samplerate, blocksize=8000, device=None, dtype='int16',
                                   channels=1, callback=self._callback_sd):
                while self.running:
                    data = self.q.get()
                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        text = res.get("text", "").lower()
                        if any(ww in text for ww in self.wake_words):
                            print(f"Wake word detected in full result: {text}")
                            if self._callback:
                                self._callback()
                                recognizer.Reset()
                                with self.q.mutex:
                                    self.q.queue.clear()
                    else:
                        res = json.loads(recognizer.PartialResult())
                        text = res.get("partial", "").lower()
                        if any(ww in text for ww in self.wake_words):
                            print(f"Wake word detected in partial result: {text}")
                            if self._callback:
                                self._callback()
                                recognizer.Reset()
                                with self.q.mutex:
                                    self.q.queue.clear()
        except Exception as e:
            print(f"WakeWordDetector error: {e}")

    def start(self, callback):
        if self.running:
            return
        self._callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
