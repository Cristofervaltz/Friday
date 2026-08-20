# Project: Friday Optimization & Hardening

## Architecture
Friday is a desktop AI assistant comprising:
- **FastAPI / WebSocket Server (`src/api/server.py`)**: Asynchronous REST & WebSocket gateway mediating communication between the frontend and the core agent.
- **Agent Core & REPL (`src/core/`, `src/cli/repl.py`, `src/runtime/`)**: Autonomous LLM agent with dynamic tool calling, memory management, and provider bindings.
- **Speech & Audio Subsystem (`src/speech/`)**: Wake-word detector daemon (`wake_word.py`), EdgeTTS audio generator (`tts_provider.py`), and Google Speech Recognition (`google_provider.py`).
- **Plugins & MCP Client (`src/plugins/`)**: Dynamic plugin loading and background MCP client process managers.
- **Process Executor (`src/executor/`)**: Windows-safe command execution engine.
- **React Frontend (`src/ui/`)**: React 19 + TypeScript + Vite + Tailwind/CSS UI with chat streaming, workspace selector, settings modal, voice panel, and Tauri 2 sidecar bridge.

```
+--------------------------------------------------------------------------+
|                           React UI (src/ui)                              |
|   App.tsx (Memoized Chat, Stable Callbacks) <-> Tauri Bridge / WebSocket |
+------------------------------------+-------------------------------------+
                                     | WS / HTTP
+------------------------------------v-------------------------------------+
|                      FastAPI Server (src/api/server.py)                   |
|   Lifespan Manager | Non-blocking Disk I/O | Managed Agent Task Pool     |
+----+-------------------------------+-------------------------------+-----+
     |                               |                               |
+----v--------------------+   +------v--------------------+   +------v-----+
| Agent Core (src/core)   |   | Speech Engine (src/speech)|   | MCP Plugins|
| Memory, Tools, LLMs     |   | WakeWord, EdgeTTS, Pygame |   | Child Procs|
+-------------------------+   +---------------------------+   +------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Non-blocking Settings I/O | Async offloading of `load_settings` / `save_settings` / `reload_config` via `asyncio.to_thread` | M1 | Survey (R1) |
| 2 | Non-blocking Chat Memory I/O | Convert `get_all_chats`, `switch_chat`, `rename_chat`, `delete_chat` to `asyncio.to_thread` | M1 | Survey (R1) |
| 3 | Non-blocking Workspace I/O | Convert `get_workspaces` and `set_workspace` disk reads/writes to `asyncio.to_thread` | M1 | Survey (R1) |
| 4 | FastAPI Lifespan & Shutdown | Replace deprecated `@app.on_event` with async lifespan context manager managing full shutdown | M1 | Survey (R1) |
| 5 | Managed Agent Task Registry | Replace unbounded `threading.Thread(target=run_friday)` with tracked async tasks / worker thread pool | M1 | Survey (R1) |
| 6 | WakeWord Queue Timeout | Add timeout to `WakeWordDetector` queue get loop to enable rapid, clean termination on `stop()` | M1 | Survey (R1) |
| 7 | Pygame & Audio Cleanup | Ensure `pygame.mixer.quit()` is invoked cleanly upon server/runtime shutdown | M1 | Survey (R1) |
| 8 | MCP Client Graceful Shutdown | Implement `shutdown_all_plugins` on `ToolRegistry` to terminate background MCP event loops/processes | M1 | Survey (R1) |
| 9 | Windows Process Tree Cleanup | Ensure spawned commands and child processes terminate cleanly with parent | M1 | Survey (R1) |
| 10 | Type Narrowing in Agent Core | Fix 3 `mypy` union-attr errors in `src/core/agent.py` | M1 | Survey (R4) |
| 11 | Chat Message Item Memoization | Extract and wrap `<ChatMessageItem>` and `<ToolBlock>` in `React.memo` to eliminate O(N*M) token re-renders | M2 | Survey (R2) |
| 12 | Stable Action Handlers | Wrap all action callbacks (`handleAction`, `handleSubmit`, `handleInstantSend`, etc.) in `useCallback` | M2 | Survey (R2) |
| 13 | Component Memoization | Wrap `Sidebar`, `WorkspaceSelector`, `AgentDashboard`, `VoicePanel`, `SettingsModal`, `CreateProjectModal` in `React.memo` | M2 | Survey (R2) |
| 14 | Artifact & Markdown Memoization | Memoize markdown plugins and custom components in `ArtifactRenderer` and `Mermaid` | M2 | Survey (R2) |
| 15 | Context Value Stabilization | Memoize `I18nProvider` value object with `useMemo` | M2 | Survey (R2) |
| 16 | Informal Comments Preservation | Preserve and ensure required informal casual comments in `App.tsx` and CLI to pass comment audits | M2 | Survey (R4) |
| 17 | Full Feature Preservation | Ensure voice recognition, LLM generation, tool execution, settings hot-reload remain 100% operational | M1, M2, M3 | Survey (R3) |
| 18 | E2E Concurrency & Shutdown Verification | Verify zero orphaned Python processes, thread termination, and server lifespan clean exit | M3 | Survey (R1, R4) |
| 19 | Frontend Build & Typecheck Verification | Verify `npm run build`, `npx tsc --noEmit`, `npm run lint`, TS stress tests (80/80), i18n checks (1302/1302) | M3 | Survey (R2, R4) |
| 20 | Multi-tier Regression & Adversarial Hardening | Pass 100% of pytest suite (439+ tests), ruff, mypy, and adversarial coverage hardening (Tier 5) | M3 | Survey (R4) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Concurrency & Lifespan Shutdown | Refactor blocking I/O in `server.py`, add FastAPI lifespan, fix wake word queue timeout, Pygame cleanup, MCP shutdown, fix mypy in `agent.py` | None | DONE |
| M2 | Frontend React Optimization & Memoization | Memoize `ChatMessageItem`, `ToolBlock`, `Sidebar`, `ArtifactRenderer`, modals, stabilize callbacks with `useCallback`, preserve informal comments | None | DONE |
| M3 | Final Integration, E2E Verification & Adversarial Hardening | Phase 1: 100% pass of E2E tests (Tiers 1-4). Phase 2: Adversarial coverage hardening (Tier 5), verify zero zombies, ruff & mypy clean | M1, M2 | DONE |

## Interface Contracts

### FastAPI Lifespan & Server Lifecycle
- `lifespan(app: FastAPI)`:
  - Startup: Initialize running loop reference, start wake word detector if enabled.
  - Shutdown: Stop wake word detector, stop active TTS, invoke `pygame.mixer.quit()`, shut down all MCP clients via `ToolRegistry.shutdown_all_plugins()`, invoke `friday_app.shutdown()`, release runtime port.

### Server WebSocket & Concurrency
- Asynchronous offloading: All synchronous disk I/O (`load_settings`, `save_settings`, `get_all_chats`, `switch_chat`, `rename_chat`, `delete_chat`, `get_workspaces`, `set_workspace`) must use `await asyncio.to_thread(...)`.
- WebSocket message dispatch: Run agent invocation in tracked asyncio tasks or thread pool, checking `websocket.client_state == WebSocketState.CONNECTED` before sending frames.

### Frontend React Component Contracts
- `<ChatMessageItem msg={msg} t={t} />`: Pure memoized component (`React.memo`). Re-renders ONLY when `msg.id`, `msg.content`, or `msg.role` changes.
- `<ArtifactRenderer content={content} />`: Pure memoized component. Uses module-level static plugin array `[remarkGfm]` and memoized `components` mapping.
- `<Sidebar onAction={...} connected={...} chats={...} currentChatId={...} />`: Pure memoized component with stabilized callback references.

## Code Layout
- Backend Server: `src/api/server.py`
- Agent Core: `src/core/agent.py`, `src/core/tool_registry.py`
- Speech & Audio: `src/speech/wake_word.py`, `src/speech/tts_provider.py`
- Frontend UI: `src/ui/src/App.tsx`, `src/ui/src/components/*`, `src/ui/src/i18n/I18nContext.tsx`
- Tests: `tests/*`
