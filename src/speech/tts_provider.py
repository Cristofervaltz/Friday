import asyncio
import os
import re
import tempfile
import threading
from typing import Any

import edge_tts
import pygame


class EdgeTTSProvider:
    """A free, high-quality Text-to-Speech provider using Microsoft Edge TTS."""

    def __init__(self, voice: str = "ru-RU-SvetlanaNeural") -> None:
        self.voice = voice
        self._stop_event = threading.Event()
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def speak(self, text: str) -> None:
        """Synthesize speech and play it synchronously."""
        if not text.strip():
            return

        # Strip emojis and special formatting before speaking
        text = re.sub(r'[^\w\s.,!?:;\'"()А-Яа-яЁё-]', "", text)
        # Split by sentence boundaries (.!?) followed by space or newline
        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return

        self._stop_event.clear()

        async def _process_all() -> None:
            queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=10)

            async def _download_worker() -> None:
                for sentence in sentences:
                    if self._stop_event.is_set():
                        break
                    communicate = edge_tts.Communicate(sentence, self.voice)
                    fd, path = tempfile.mkstemp(suffix=".mp3")
                    os.close(fd)
                    try:
                        await communicate.save(path)
                        await queue.put(path)
                    except Exception:
                        pass
                await queue.put(None)  # Signal done

            downloader = asyncio.create_task(_download_worker())

            while not self._stop_event.is_set():
                path = await queue.get()
                if path is None:
                    break

                try:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while (
                        pygame.mixer.music.get_busy() and not self._stop_event.is_set()
                    ):
                        await asyncio.sleep(0.1)
                finally:
                    pygame.mixer.music.unload()
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            while not queue.empty():
                path = queue.get_nowait()
                if path is not None:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            if not downloader.done():
                downloader.cancel()

        asyncio.run(_process_all())

    def stop(self) -> None:
        """Stop current playback."""
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
