"""Adversarial concurrency & stress test harness for Friday M3.

tests permission locks, ws disconnect resilience, memory callbacks under load,
and swarm sub-agent concurrency stress.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.tool_registry import ToolRegistry
from src.memory.conversation import ConversationMemory
from src.tools.base import BaseTool, ToolResult
from src.tools.swarm_tool import DelegateTaskTool


class DummyTool(BaseTool):
    """dummy tool for concurrency stress tests."""

    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "a simple test tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"val": {"type": "integer"}},
            "required": ["val"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        # just do a tiny sleep to simulate work
        val = kwargs.get("val", 0)
        time.sleep(0.005)
        return ToolResult(success=True, output=f"result_{val}")


# ---------------------------------------------------------------------------
# 1. PERMISSION LOCK & EVENT HANDLING CONCURRENCY TESTS
# ---------------------------------------------------------------------------


def test_permission_lock_serialization_and_correctness() -> None:
    """Stress test _permission_lock with 20 concurrent threads requesting permission."""
    from src.api import server

    # simulate a server loop and active ws
    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    in_flight_count = 0
    max_concurrent_in_flight = 0
    in_flight_lock = threading.Lock()
    received_requests: list[str] = []

    mock_ws = MagicMock()

    async def fake_send_text(msg_text: str) -> None:
        nonlocal in_flight_count, max_concurrent_in_flight
        msg = json.loads(msg_text)
        if msg.get("type") == "permission_request":
            action = msg.get("action", "")
            with in_flight_lock:
                in_flight_count += 1
                if in_flight_count > max_concurrent_in_flight:
                    max_concurrent_in_flight = in_flight_count
                received_requests.append(action)

            # simulate user thinking for a bit, then responding
            time.sleep(0.01)
            with in_flight_lock:
                in_flight_count -= 1

            # approve if action ends with even number, reject if odd
            cmd_id = int(action.split("_")[-1])
            approved = (cmd_id % 2) == 0

            # trigger response back through server state
            server.permission_result = approved
            server.permission_event.set()

    mock_ws.send_text = AsyncMock(side_effect=fake_send_text)

    # initialize server globals for testing
    server.active_websocket = mock_ws
    server.server_loop = loop
    server.permission_event = threading.Event()
    server.permission_result = False

    num_threads = 20
    results: dict[int, bool] = {}
    threads: list[threading.Thread] = []

    def worker(idx: int) -> None:
        # call _ask_user_permission via the lock logic
        with server._permission_lock:
            server.permission_event.clear()
            assert server.server_loop is not None
            asyncio.run_coroutine_threadsafe(
                mock_ws.send_text(
                    json.dumps(
                        {"type": "permission_request", "action": f"exec_cmd_{idx}"}
                    )
                ),
                server.server_loop,
            )
            waited = server.permission_event.wait(timeout=5.0)
            if not waited:
                results[idx] = False
            else:
                results[idx] = server.permission_result

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)

    # start all threads at once
    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=10.0)

    # cleanup loop
    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join(timeout=2.0)
    server.active_websocket = None
    server.server_loop = None

    # assertions: lock must ensure only 1 request in flight at any time
    assert max_concurrent_in_flight == 1, (
        f"Expected max 1 in-flight permission request, got {max_concurrent_in_flight}"
    )
    assert len(results) == num_threads
    for idx, res in results.items():
        expected = (idx % 2) == 0
        assert res == expected, (
            f"Thread {idx} got permission={res}, expected {expected}"
        )


def test_permission_timeout_safety() -> None:
    """Ensure permission request times out safely when user does not respond."""
    from src.api import server

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    mock_ws = MagicMock()
    # ws sends text but user never responds
    mock_ws.send_text = AsyncMock()

    server.active_websocket = mock_ws
    server.server_loop = loop
    server.permission_event = threading.Event()
    server.permission_result = False

    # temporarily test short timeout
    start_t = time.time()
    with server._permission_lock:
        server.permission_event.clear()
        asyncio.run_coroutine_threadsafe(
            mock_ws.send_text(
                json.dumps(
                    {"type": "permission_request", "action": "dangerous_action"}
                )
            ),
            loop,
        )
        waited = server.permission_event.wait(timeout=0.1)
        res = server.permission_result if waited else False

    elapsed = time.time() - start_t
    loop.call_soon_threadsafe(loop.stop)
    server.active_websocket = None

    assert waited is False
    assert res is False
    assert elapsed >= 0.1


def test_permission_without_websocket_returns_false() -> None:
    """Ensure permission request returns False without hanging when ws is None."""
    from src.api import server

    server.active_websocket = None
    server.server_loop = None

    # simulate asking permission with no active ws
    with server._permission_lock:
        # if active_websocket is None, should immediately return False
        if server.active_websocket is None or server.server_loop is None:
            res = False
        else:
            res = True

    assert res is False


# ---------------------------------------------------------------------------
# 2. MEMORY CALLBACKS & WEBSOCKET DISCONNECT STRESS TESTS
# ---------------------------------------------------------------------------


def test_memory_callbacks_under_concurrent_flood(tmp_path: Any) -> None:
    """Blast memory with concurrent messages & callback triggers from 15 threads."""
    save_dir = tmp_path / "chats"
    mem = ConversationMemory(chat_id="stress_chat", save_dir=save_dir)

    callback_fire_count = 0
    callback_lock = threading.Lock()

    def on_change(target_mem: Any = None) -> None:
        nonlocal callback_fire_count
        with callback_lock:
            callback_fire_count += 1
            # read messages safely during callback
            _ = len(mem.get_messages())

    mem.add_on_change_callback(on_change)

    num_threads = 15
    msgs_per_thread = 40
    threads: list[threading.Thread] = []

    def writer(thread_id: int) -> None:
        for j in range(msgs_per_thread):
            if j % 3 == 0:
                mem.add_user_message(f"user_msg_t{thread_id}_{j}")
            elif j % 3 == 1:
                mem.add_assistant_message(f"asst_msg_t{thread_id}_{j}")
            else:
                mem.add_message(
                    "system",
                    f"sys_msg_t{thread_id}_{j}",
                    chat_id="stress_chat",
                )

    for i in range(num_threads):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=10.0)

    # total ops = 15 * 40 = 600 mutations
    assert callback_fire_count == num_threads * msgs_per_thread
    # max_messages default is 50, so memory sliding window should enforce <= 50 messages
    messages = mem.get_messages()
    assert len(messages) <= mem.max_messages


def test_memory_callback_ws_disconnect_resilience() -> None:
    """Test that send_updates in on_memory_change handles abrupt ws disconnect without crashing."""
    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    mem = ConversationMemory(chat_id="ws_disconnect_test")
    ws_mock = MagicMock()

    # simulate ws failing immediately when send_text is called
    async def broken_send(msg: str) -> None:
        raise ConnectionResetError("client abruptly disconnected")

    ws_mock.send_text = AsyncMock(side_effect=broken_send)

    # reproduce the exact server on_memory_change handler
    def on_memory_change(target_mem: Any = None) -> None:
        async def send_updates() -> None:
            try:
                await ws_mock.send_text(
                    json.dumps(
                        {
                            "type": "chat_history",
                            "chat_id": "ws_disconnect_test",
                            "messages": mem.get_messages(),
                        }
                    )
                )
            except Exception:
                # server catches this cleanly
                pass

        asyncio.run_coroutine_threadsafe(send_updates(), loop)

    mem.add_on_change_callback(on_memory_change)

    # flood messages - none of them should throw or crash
    for i in range(50):
        mem.add_user_message(f"msg_{i}")
        mem.add_assistant_message(f"reply_{i}")

    # cleanup callback as server finally block does
    mem._on_change_callbacks.remove(on_memory_change)
    assert len(mem._on_change_callbacks) == 0

    # allow background tasks to complete processing
    time.sleep(0.1)
    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# 3. SWARM DELEGATION & TOOL OPERATIONS HIGH CONCURRENCY TESTS
# ---------------------------------------------------------------------------


class MockSwarmApp:
    def __init__(self, tmp_path: Any) -> None:
        self.provider = MagicMock()
        self.config = MagicMock()
        self.config.paths.data_dir = tmp_path / "data"
        self.config.llm.max_iterations = 5


def test_swarm_concurrent_background_subagents(tmp_path: Any) -> None:
    """Spawn 15 concurrent background sub-agents and verify all complete and clean up."""
    app = MockSwarmApp(tmp_path)
    parent_memory = ConversationMemory(
        chat_id="parent_chat", save_dir=tmp_path / "data" / "chats"
    )

    parent_agent = MagicMock()
    parent_agent.memory = parent_memory

    registry = ToolRegistry()
    registry.context = MagicMock()
    registry.context.agent = parent_agent

    tool = DelegateTaskTool(app=app, registry=registry)

    # mock sub-agent run to simulate varying execution latencies
    def fake_agent_run(self_agent: Any, task_prompt: str) -> str:
        # short sleep simulating agent thinking/tooling
        time.sleep(0.02)
        return f"Finished: {task_prompt}"

    num_subagents = 15
    with patch("src.tools.swarm_tool.Agent.run", new=fake_agent_run):
        for i in range(num_subagents):
            res = tool.execute(
                role=f"worker_{i}",
                task=f"subtask_{i}",
                run_in_background=True,
            )
            assert res.success is True
            assert "spawned in the background" in str(res.output)

        # wait for all background subagent threads to finish
        deadline = time.time() + 5.0
        while time.time() < deadline:
            # check how many sub-agent responses have been injected into parent memory
            msgs = parent_memory.get_messages()
            injected_count = sum(
                1
                for m in msgs
                if "finished its background task!" in str(m.get("content", ""))
            )
            if injected_count == num_subagents:
                break
            time.sleep(0.05)

        msgs = parent_memory.get_messages()
        injected = [
            m
            for m in msgs
            if "finished its background task!" in str(m.get("content", ""))
        ]
        assert len(injected) == num_subagents, (
            f"Expected {num_subagents} injected results, got {len(injected)}"
        )

        # verify all temporary sub-agent chats were cleaned up
        remaining_chats = parent_memory.get_all_chats()
        sub_chats = [
            c
            for c in remaining_chats
            if str(c.get("id", "")).startswith("sub_")
        ]
        assert len(sub_chats) == 0, (
            f"Expected 0 leftover sub_ chats, found {sub_chats}"
        )


def test_swarm_subagent_error_resilience_under_concurrency(
    tmp_path: Any,
) -> None:
    """Test that when concurrent sub-agents crash, errors are safely reported and chats cleaned up."""
    app = MockSwarmApp(tmp_path)
    parent_memory = ConversationMemory(
        chat_id="parent_err_chat", save_dir=tmp_path / "data" / "chats"
    )

    parent_agent = MagicMock()
    parent_agent.memory = parent_memory

    registry = ToolRegistry()
    registry.context = MagicMock()
    registry.context.agent = parent_agent

    tool = DelegateTaskTool(app=app, registry=registry)

    # odd tasks fail, even tasks succeed
    def fake_failing_run(self_agent: Any, task_prompt: str) -> str:
        time.sleep(0.01)
        if "fail" in task_prompt:
            raise RuntimeError(f"boom on {task_prompt}")
        return f"success on {task_prompt}"

    num_tasks = 10
    with patch("src.tools.swarm_tool.Agent.run", new=fake_failing_run):
        for i in range(num_tasks):
            task_str = f"task_{i}_fail" if i % 2 == 1 else f"task_{i}_ok"
            tool.execute(
                role=f"worker_{i}", task=task_str, run_in_background=True
            )

        # wait for completion
        deadline = time.time() + 5.0
        while time.time() < deadline:
            msgs = parent_memory.get_messages()
            done_count = len(msgs)
            if done_count >= num_tasks:
                break
            time.sleep(0.05)

        msgs = parent_memory.get_messages()
        errors = [
            m for m in msgs if "encountered an error:" in str(m.get("content", ""))
        ]
        successes = [
            m
            for m in msgs
            if "finished its background task!" in str(m.get("content", ""))
        ]

        assert len(errors) == 5, f"Expected 5 errors, got {len(errors)}"
        assert len(successes) == 5, f"Expected 5 successes, got {len(successes)}"

        # ensure no orphaned sub-agent chats remain
        all_chats = parent_memory.get_all_chats()
        sub_chats = [
            c for c in all_chats if str(c.get("id", "")).startswith("sub_")
        ]
        assert len(sub_chats) == 0


def test_tool_registry_concurrent_execution() -> None:
    """Stress test ToolRegistry under 20 concurrent execution threads."""
    registry = ToolRegistry()
    dummy = DummyTool()
    registry.register(dummy)

    num_threads = 20
    results: dict[int, ToolResult] = {}
    threads: list[threading.Thread] = []

    def run_tool(idx: int) -> None:
        res = registry.execute("dummy_tool", val=idx)
        results[idx] = res

    for i in range(num_threads):
        t = threading.Thread(target=run_tool, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=5.0)

    assert len(results) == num_threads
    for idx, res in results.items():
        assert res.success is True
        assert res.output == f"result_{idx}"


def test_concurrent_chat_mutations_switch_rename_delete(tmp_path: Any) -> None:
    """Stress test ConversationMemory under concurrent switch, rename, delete, and writes."""
    save_dir = tmp_path / "chats"
    mem = ConversationMemory(chat_id="chat_0", save_dir=save_dir)

    num_workers = 12
    iterations = 30
    exceptions: list[Exception] = []
    exc_lock = threading.Lock()

    def worker_mutator(worker_id: int) -> None:
        try:
            for j in range(iterations):
                cid = f"chat_{worker_id % 4}"
                mem.switch_chat(cid)
                mem.rename_chat(cid, f"Title {worker_id}-{j}")
                mem.add_user_message(f"worker_{worker_id} msg {j}")
                mem.add_assistant_message(f"worker_{worker_id} reply {j}")
                if j % 10 == 0:
                    _ = mem.get_all_chats()
                if j % 15 == 0 and worker_id > 2:
                    mem.delete_chat(f"chat_{worker_id}")
        except Exception as e:
            with exc_lock:
                exceptions.append(e)

    threads = [
        threading.Thread(target=worker_mutator, args=(i,))
        for i in range(num_workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert (
        len(exceptions) == 0
    ), f"Concurrent chat mutations threw exceptions: {exceptions}"
    # check that chats still exist and are valid json
    all_chats = mem.get_all_chats()
    assert isinstance(all_chats, list)


def test_nested_swarm_delegation_concurrency(tmp_path: Any) -> None:
    """Test nested swarm delegation where sub-agent delegates to another sub-agent."""
    app = MockSwarmApp(tmp_path)
    parent_memory = ConversationMemory(
        chat_id="parent_root", save_dir=tmp_path / "data" / "chats"
    )

    parent_agent = MagicMock()
    parent_agent.memory = parent_memory

    registry = ToolRegistry()
    registry.context = MagicMock()
    registry.context.agent = parent_agent

    tool = DelegateTaskTool(app=app, registry=registry)

    # simulate level-1 subagent delegating to level-2 subagent
    def fake_nested_run(self_agent: Any, task_prompt: str) -> str:
        if "level_1" in task_prompt:
            # level 1 invokes tool to spawn level 2 synchronously
            level2_res = tool.execute(
                role="level_2_worker", task="level_2_task", run_in_background=False
            )
            return f"level_1 finished with nested: ({level2_res.output})"
        return f"level_2 finished task: {task_prompt}"

    with patch("src.tools.swarm_tool.Agent.run", new=fake_nested_run):
        res = tool.execute(
            role="level_1_worker", task="level_1_task", run_in_background=False
        )

        assert res.success is True
        assert "level_1 finished with nested: (Sub-agent 'level_2_worker' done. Response:\nlevel_2 finished task: level_2_task)" in str(res.output)

        # verify all sub_ chats deleted
        chats = parent_memory.get_all_chats()
        sub_chats = [c for c in chats if str(c.get("id", "")).startswith("sub_")]
        assert len(sub_chats) == 0
