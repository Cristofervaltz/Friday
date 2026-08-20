"""Text-to-Speech provider using Edge TTS and Pygame mixer."""

import asyncio
import os
import re
import tempfile
import threading
from typing import Any

import edge_tts
import pygame

_mixer_lock = threading.RLock()


def _ensure_mixer_init() -> None:
    """Ensure pygame mixer is initialized safely."""
    with _mixer_lock:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            pass


def cleanup_audio_subsystem() -> None:
    """Cleanly stop playback and quit pygame mixer to release audio hardware handles."""
    with _mixer_lock:
        try:
            if pygame.mixer.get_init():
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                pygame.mixer.quit()
        except Exception:
            pass


class EdgeTTSProvider:
    """A free, high-quality Text-to-Speech provider using Microsoft Edge TTS."""

    def __init__(self, voice: str = "ru-RU-SvetlanaNeural") -> None:
        self.voice = voice
        self._stop_event = threading.Event()
        _ensure_mixer_init()

    def _clean_and_split(self, text: str) -> list[str]:
        if not text.strip():
            return []
        # Strip code blocks, emojis, and special formatting before speaking
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r'[^\w\s.,!?:;\'"()А-Яа-яЁё-]', "", text)
        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def _process_all(self, sentences: list[str]) -> None:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=10)
        created_files: set[str] = set()

        async def _download_worker() -> None:
            for sentence in sentences:
                if self._stop_event.is_set():
                    break
                fd, path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                created_files.add(path)
                try:
                    communicate = edge_tts.Communicate(sentence, self.voice)
                    await communicate.save(path)
                    if self._stop_event.is_set():
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                        created_files.discard(path)
                        break
                    await queue.put(path)
                except Exception:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    created_files.discard(path)
            await queue.put(None)  # Signal done

        downloader = asyncio.create_task(_download_worker())

        try:
            while not self._stop_event.is_set():
                try:
                    path = await asyncio.wait_for(queue.get(), timeout=0.2)
                except TimeoutError:
                    continue

                if path is None:
                    break

                try:
                    with _mixer_lock:
                        if pygame.mixer.get_init() and not self._stop_event.is_set():
                            pygame.mixer.music.load(path)
                            pygame.mixer.music.play()

                    while not self._stop_event.is_set():
                        is_busy = False
                        with _mixer_lock:
                            if pygame.mixer.get_init():
                                is_busy = pygame.mixer.music.get_busy()
                        if not is_busy:
                            break
                        await asyncio.sleep(0.05)
                except Exception:
                    pass
                finally:
                    with _mixer_lock:
                        try:
                            if pygame.mixer.get_init():
                                pygame.mixer.music.unload()
                        except Exception:
                            pass
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    created_files.discard(path)
        finally:
            if not downloader.done():
                downloader.cancel()
                try:
                    await downloader
                except (asyncio.CancelledError, Exception):
                    pass

            while not queue.empty():
                try:
                    p = queue.get_nowait()
                    if p and isinstance(p, str):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                        created_files.discard(p)
                except Exception:
                    break

            for remaining in list(created_files):
                try:
                    os.remove(remaining)
                except OSError:
                    pass
                created_files.discard(remaining)

    def speak(self, text: str) -> None:
        """Synthesize speech and play it. Safe across sync and worker threads."""
        sentences = self._clean_and_split(text)
        if not sentences:
            return

        self._stop_event.clear()
        _ensure_mixer_init()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(lambda: asyncio.run(self._process_all(sentences))).result()
        else:
            asyncio.run(self._process_all(sentences))

    async def speak_async(self, text: str) -> None:
        """Synthesize speech and play it asynchronously within an existing event loop."""
        sentences = self._clean_and_split(text)
        if not sentences:
            return
        self._stop_event.clear()
        _ensure_mixer_init()
        await self._process_all(sentences)

    def stop(self) -> None:
        """Stop current playback immediately and release audio track."""
        self._stop_event.set()
        with _mixer_lock:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            except Exception:
                pass

    def cleanup(self) -> None:
        """Stop playback and cleanly quit audio mixer."""
        self.stop()
        cleanup_audio_subsystem()
