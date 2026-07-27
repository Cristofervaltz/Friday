import os
import asyncio
import tempfile
import pygame
import edge_tts


class EdgeTTSProvider:
    """A free, high-quality Text-to-Speech provider using Microsoft Edge TTS."""

    def __init__(self, voice: str = "ru-RU-SvetlanaNeural") -> None:
        self.voice = voice
        pygame.mixer.init()

    def speak(self, text: str) -> None:
        """Synthesize speech and play it synchronously."""
        if not text.strip():
            return

        async def _generate_audio() -> str:
            communicate = edge_tts.Communicate(text, self.voice)
            fd, path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            await communicate.save(path)
            return path

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Generate the audio file
        path = loop.run_until_complete(_generate_audio())

        # Play it using pygame
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        finally:
            pygame.mixer.music.unload()
            try:
                os.remove(path)
            except OSError:
                pass
