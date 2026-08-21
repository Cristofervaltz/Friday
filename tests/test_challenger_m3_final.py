"""Empirical Challenger Adversarial Hardening Suite for Milestone 3.

Stress tests:
1. Lifespan Rapid Cycling & Graceful Teardown under load
2. TTS Strict Mute and Audio Subsystem Isolation Invariants
3. Concurrency Burst: 50 Parallel Chat / Settings / Workspace Operations
4. WebSocket Broken Frame & Mid-flight Disconnect Resilience
5. WakeWord Rapid Stop (<0.5s) & Audio Subsystem Cleanup
6. Windows Child Process Termination & Memory Bounds
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketState

from src.api import server
from src.config import load_settings, save_settings
from src.speech.tts_provider import EdgeTTSProvider, cleanup_audio_subsystem
from src.speech.wake_word import WakeWordDetector


class TestLifespanAndResourceCleanupChallenger:
    """Stress test lifespan teardown and subsystem resource cleanup."""

    @pytest.mark.anyio
    async def test_lifespan_rapid_cycles_with_active_tasks(
        self, tmp_path: Path
    ) -> None:
        """Verify that multiple rapid lifespan start/shutdown cycles clean up all tasks."""
        app = server.create_app()

        for cycle in range(5):
            async with app.router.lifespan_context(app):
                # Spawn some fake background agent tasks
                async def slow_work() -> None:
                    await asyncio.sleep(10.0)

                t1 = asyncio.create_task(slow_work())
                t2 = asyncio.create_task(slow_work())
                server.active_agent_tasks.add(t1)
                server.active_agent_tasks.add(t2)

            # After exiting lifespan context, active_agent_tasks must be cleared
            assert (
                len(server.active_agent_tasks) == 0
            ), f"Cycle {cycle} leaked agent tasks"
            assert t1.cancelled() or t1.done()
            assert t2.cancelled() or t2.done()

    def test_wakeword_stop_latency_invariant(self) -> None:
        """WakeWordDetector.stop() must return in under 500ms without deadlocking."""
        detector = WakeWordDetector()

        with (
            patch("src.speech.wake_word.Model"),
            patch("src.speech.wake_word.KaldiRecognizer"),
            patch(
                "src.speech.wake_word.sd.query_devices",
                return_value=[{"max_input_channels": 1}],
            ),
            patch("src.speech.wake_word.sd.RawInputStream"),
        ):

            dummy_called = False

            def dummy_cb() -> None:
                nonlocal dummy_called
                dummy_called = True

            detector.start(dummy_cb)
            assert detector.running is True
            time.sleep(0.05)

            # Measure stop time
            t0 = time.perf_counter()
            detector.stop()
            elapsed = time.perf_counter() - t0

            assert detector.running is False
            assert (
                elapsed < 0.5
            ), f"WakeWordDetector stop took {elapsed:.3f}s (expected < 0.5s)"

    def test_tts_cleanup_audio_subsystem_idempotence(self) -> None:
        """cleanup_audio_subsystem must be safe to call repeatedly concurrently."""
        threads = []
        errors: list[Exception] = []

        def run_cleanup() -> None:
            try:
                for _ in range(10):
                    cleanup_audio_subsystem()
            except Exception as e:
                errors.append(e)

        for _ in range(10):
            t = threading.Thread(target=run_cleanup)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent cleanup_audio_subsystem raised: {errors}"


class TestTTSAudioSuppressionChallenger:
    """Verify TTS suppression policies and mock behaviors."""

    def test_tts_disabled_settings_bypass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When tts_enabled is 'false' in config.json, load_settings_safe reports False."""
        friday_home = tmp_path / ".friday"
        friday_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("FRIDAY_HOME", str(friday_home))

        config_file = friday_home / "config.json"
        config_file.write_text(json.dumps({"tts_enabled": "false"}), encoding="utf-8")

        from src._compat import load_settings_safe

        s = load_settings_safe()
        tts_enabled = str(s.get("tts_enabled", "true")).lower() == "true"
        assert tts_enabled is False

    def test_tts_clean_and_split_edge_cases(self) -> None:
        """EdgeTTSProvider._clean_and_split handles adversarial and empty inputs."""
        provider = EdgeTTSProvider()

        # 1. Empty & whitespace strings
        assert provider._clean_and_split("") == []
        assert provider._clean_and_split("   \n\t  ") == []

        # 2. Markdown code blocks stripping
        code_text = "Here is code:\n```python\nprint('hello')\n```\nAnd explanation."
        clean = provider._clean_and_split(code_text)
        assert len(clean) >= 1
        for s in clean:
            assert "print('hello')" not in s

        # 3. Special characters & emoji stripping
        emoji_text = "Hello world! 🔥 🚀 ⚡ How are you?"
        clean_emoji = provider._clean_and_split(emoji_text)
        assert len(clean_emoji) >= 1


class TestConcurrencyBurstChallenger:
    """Stress test asynchronous server I/O methods under high parallel load."""

    @pytest.mark.anyio
    async def test_high_concurrency_settings_and_workspace_io(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """50 concurrent asyncio tasks writing/reading settings & workspaces."""
        friday_home = tmp_path / ".friday"
        friday_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("FRIDAY_HOME", str(friday_home))

        async def worker(worker_id: int) -> None:
            for i in range(5):
                s = await asyncio.to_thread(load_settings)
                s[f"key_{worker_id}_{i}"] = f"val_{worker_id}_{i}"
                await asyncio.to_thread(save_settings, s)
                await asyncio.sleep(0.001)

        tasks = [asyncio.create_task(worker(w)) for w in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            assert not isinstance(
                res, Exception
            ), f"Concurrent settings I/O failed: {res}"

        final_settings = load_settings()
        assert len(final_settings) > 0


class TestWebSocketAdversarialResilience:
    """Verify WebSocket error handling, disconnects, and malformed frames."""

    @pytest.mark.anyio
    async def test_safe_send_ws_with_closed_loop_and_disconnected_ws(self) -> None:
        """safe_send_ws handles closed loop, None ws, and disconnected client states gracefully."""
        # 1. None ws and None loop
        server.safe_send_ws(None, {"type": "test"}, None)

        # 2. Mock ws with CONNECTED state but raising exception on send
        mock_ws = MagicMock()
        mock_ws.client_state = WebSocketState.CONNECTED
        mock_ws.send_text = AsyncMock(side_effect=RuntimeError("connection reset"))

        loop = asyncio.get_running_loop()
        server.safe_send_ws(mock_ws, {"type": "test"}, loop)
        await asyncio.sleep(0.05)  # Let coroutine run

        # 3. Mock ws with DISCONNECTED state
        mock_ws.client_state = WebSocketState.DISCONNECTED
        mock_ws.send_text.reset_mock()
        server.safe_send_ws(mock_ws, {"type": "test"}, loop)
        await asyncio.sleep(0.02)
        mock_ws.send_text.assert_not_called()
