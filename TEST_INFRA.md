# 5-Tier End-to-End Test Infrastructure Specification

## 1. Test Philosophy & Principles
Friday's test infrastructure is built upon a **requirement-driven, opaque-box, and white-box adversarial verification methodology**. All test suites execute against real state, concrete message dispatch loops, actual async/thread boundaries, and genuine subsystem behaviors rather than relying on shallow stubs or dummy facades.

### Core Testing Tenets
1. **Opaque-Box Requirement Verification**: Core user workflows (chat streaming, voice interaction, tool execution, workspace switching, settings manipulation) are verified at boundaries (WebSocket JSON frames, REST endpoints, CLI inputs, React event state machines) to ensure real-world contract adherence.
2. **Deterministic Process & Concurrency Control**: Multi-threaded concurrency, async event loops, and Windows subprocess trees are exercised under burst loads with explicit timeouts, cancellation tokens, and zero zombie process leakage.
3. **Multi-Tier Quality Gates**: Testing is stratified into 5 distinct tiers (Isolation, Boundaries, Cross-Feature Pairwise, Real-World Workloads, Concurrency/Shutdown Stress) to ensure no defect escapes unnoticed.
4. **Strict Static Analysis Parity**: 100% type safety (`mypy --strict`) and zero lint violations (`ruff check .`, `oxlint`, `tsc --noEmit`) are enforced across both source code and test files.
5. **Absolute Audio / TTS Suppression**: Under NO circumstances will tests emit spoken audio through system speakers. Fixture-level sandboxing in `conftest.py` enforces `tts_enabled=false` and auto-patches `EdgeTTSProvider.speak` and `EdgeTTSProvider.speak_async` with mocks across all test executions.
6. **Human-like Informal Comments Compliance**: Source files and test harnesses conform to project comment conventions without violating syntax or static analysis rules.

---

## 2. Feature Inventory & Coverage Matrix
Every feature defined in `PROJECT.md § Feature Inventory` is mapped across the 5 testing tiers with dedicated test suites and assertions:

| # | Feature Name | Primary Subsystem | Target Tiers | Test Suite Locations | Test Count / Asserts | Pass Status |
|---|--------------|-------------------|--------------|----------------------|----------------------|-------------|
| 1 | Non-blocking Settings I/O | `src/api/server.py`, `src/config/` | Tier 1, 2, 3 | `tests/test_config.py`, `tests/test_e2e_friday.py` | 14 tests | **PASS (100%)** |
| 2 | Non-blocking Chat Memory I/O | `src/memory/conversation.py` | Tier 1, 2, 3 | `tests/test_conversation_memory.py`, `tests/test_e2e_friday.py` | 18 tests | **PASS (100%)** |
| 3 | Non-blocking Workspace I/O | `src/api/server.py`, `src/tools/` | Tier 1, 2, 4 | `tests/test_e2e_friday.py`, `tests/test_list_tool.py` | 16 tests | **PASS (100%)** |
| 4 | FastAPI Lifespan & Shutdown | `src/api/server.py` | Tier 1, 5 | `tests/test_runtime.py`, `tests/test_e2e_friday.py`, `tests/test_empirical_challenger_m1.py` | 15 tests | **PASS (100%)** |
| 5 | Managed Agent Task Registry | `src/api/server.py` | Tier 1, 5 | `tests/test_concurrency_stress.py`, `tests/test_adversarial_m3.py` | 10 tests | **PASS (100%)** |
| 6 | WakeWord Queue Timeout | `src/speech/wake_word.py` | Tier 1, 2, 5 | `tests/test_e2e_friday.py`, `tests/test_empirical_challenger_m1.py` | 11 tests | **PASS (100%)** |
| 7 | Pygame & Audio Cleanup | `src/speech/tts_provider.py` | Tier 1, 5 | `tests/test_e2e_friday.py`, `tests/test_empirical_challenger_m1.py` | 8 tests | **PASS (100%)** |
| 8 | MCP Client Graceful Shutdown | `src/plugins/`, `src/core/` | Tier 1, 5 | `tests/test_plugins.py`, `tests/test_e2e_friday.py` | 7 tests | **PASS (100%)** |
| 9 | Windows Process Tree Cleanup | `src/executor/`, `src/tools/` | Tier 1, 5 | `tests/test_executor.py`, `tests/test_shell_tool.py`, `tests/test_empirical_challenger_m1.py` | 15 tests | **PASS (100%)** |
| 10 | Type Narrowing in Agent Core | `src/core/agent.py` | Tier 1 | `tests/test_agent.py`, `mypy src tests` | 8 tests + mypy | **PASS (100%)** |
| 11 | Chat Message Item Memoization | `src/ui/src/App.tsx` | Tier 1, 2 | `tests/test_frontend_stress.ts`, `tests/test_m2_challenger_deep_stress.ts` | 20 checks | **PASS (100%)** |
| 12 | Stable Action Handlers | `src/ui/src/App.tsx` | Tier 1, 3 | `tests/test_frontend_stress.ts`, `tests/test_m2_challenger_deep_stress.ts` | 25 checks | **PASS (100%)** |
| 13 | Component Memoization | `src/ui/src/components/` | Tier 1 | `tests/test_frontend_stress.ts`, `tests/test_challenger_m2_adversarial.ts` | 18 checks | **PASS (100%)** |
| 14 | Artifact & Markdown Memoization | `src/ui/src/components/` | Tier 1 | `tests/test_frontend_stress.ts`, `tests/test_m2_challenger_deep_stress.ts` | 10 checks | **PASS (100%)** |
| 15 | Context Value Stabilization | `src/ui/src/i18n/` | Tier 1, 3 | `tests/test_frontend_stress.ts`, `src/ui/verify_i18n_comprehensive.mjs` | 1302 checks | **PASS (100%)** |
| 16 | Informal Comments Preservation | `App.tsx`, `repl.py`, `i18n/` | Tier 1, 2 | `tests/test_challenger_adversarial_deep.py`, `tests/test_challenger_m2_adversarial.ts` | 29 tests | **PASS (100%)** |
| 17 | Full Feature Preservation | Tools, REPL, LLM, Speech | Tier 1, 3, 4 | `tests/test_os_tools.py`, `tests/test_llm.py`, `tests/test_repl.py` | 125 tests | **PASS (100%)** |
| 18 | E2E Concurrency & Shutdown Verification | Server, Threads, Procs | Tier 5 | `tests/test_concurrency_stress.py`, `tests/test_e2e_friday.py` | 12 tests | **PASS (100%)** |
| 19 | Frontend Build & Typecheck Verification | `src/ui/` | Tier 1, 4 | `npm run build`, `npx tsc --noEmit`, `oxlint` | Clean build & typecheck | **PASS (100%)** |
| 20 | Multi-tier Regression & Adversarial Hardening | Global System | Tier 1-5 | Full Pytest Suite (439 tests), TSX Stress (198 checks) | 637+ tests | **PASS (100%)** |

---

## 3. Test Architecture & Harness Design

```
+---------------------------------------------------------------------------------------------------+
|                                     Test Orchestration Suite                                      |
+---------------------------------------------------------------------------------------------------+
|    Python Suite (pytest)     |    Frontend Stress (tsx)    |     i18n Validation (node)           |
|    439 Tests (Tiers 1-5)     |    198 Checks (17 Suites)   |     1302 Checks (5 Suites)          |
+---------------+--------------+--------------+--------------+---------------+----------------------+
                |                             |                              |
+---------------v-----------------------------v------------------------------v----------------------+
|                                   Isolation & Mocking Layer                                       |
|  - conftest.py: tmp_path FRIDAY_HOME sandbox & environment isolation                              |
|  - Strict Audio Suppression: tts_enabled=false + EdgeTTSProvider.speak autouse mock patch         |
|  - Starlette/FastAPI TestClient: async WebSocket & REST frame driver                              |
|  - ThreadSafe Events & Permission Locks: 20-thread concurrency harness                            |
|  - MockHTTPResponse & URLLib stubs: Deterministic LLM response injection                          |
|  - AST & Regex Structural Scanners: Static comment & schema audits                                |
+---------------------------------------------------------------------------------------------------+
```

### 3.1 Directory Layout & Test Suites
- `tests/conftest.py`: Root pytest fixtures providing ephemeral sandboxes (`FRIDAY_HOME=tmp_path/.friday`), isolating ambient environment variables, and auto-suppressing all TTS speech output.
- `tests/test_e2e_friday.py`: 87 comprehensive tests implementing Tiers 1 through 5.
- `tests/test_concurrency_stress.py`: Multi-threaded permission lock stress, 20-thread burst workers, WebSocket reconnect cycles, swarm worker isolation.
- `tests/test_adversarial_m3.py`: Malformed JSON frame injections, polymorphic `rename_chat` payload formats, REPL clear permutations, tool export contracts.
- `tests/test_challenger_adversarial_deep.py`: State-machine instant-send burst queueing, i18n dot-notation resolution, parameter interpolation stress.
- `tests/test_empirical_challenger_m1.py`: Hard empirical tests for wake word stop timing (<0.5s), child process termination with Job Objects, and FastAPI lifespan teardown.
- `tests/test_frontend_stress.ts`: TypeScript/Node suite with 80 empirical assertions covering UI state machines, key parity, and placeholder symmetry.
- `tests/test_challenger_m2_adversarial.ts`: TypeScript suite with 50 assertions covering 1000-item burst queues, edge-case payloads, React memoization AST audits, and comment audits.
- `tests/test_m2_challenger_deep_stress.ts`: TypeScript suite with 68 assertions covering 500-chunk streaming re-render counts, visible message memoization, callback dependency arrays, and key stability.
- `src/ui/verify_i18n_comprehensive.mjs`: 1302 automated checks validating bilingual symmetry, Cyrillic purity, and dynamic key resolutions.

### 3.2 Fixture Strategies & Mock Isolation
- **Audio & TTS Hard Suppression**: All tests run with `tts_enabled=false` and monkeypatched `EdgeTTSProvider.speak`/`speak_async` mocks to guarantee zero auditory emissions.
- **Disk Isolation**: Tests execute in unique `tmp_path` directories preventing test-to-test side-effects.
- **Hardware Decoupling**: Microphone and audio hardware are decoupled via `unittest.mock.MagicMock` and `SpeechRecognizer` stubs, allowing tests to run headlessly in CI environments.
- **Async Event Loops**: Multi-threaded concurrency tests manage their own `asyncio.new_event_loop()` threads, dispatched via `asyncio.run_coroutine_threadsafe()`.

---

## 4. 5-Tier Testing Methodology

### Tier 1: Isolated Feature Verification
Verifies each feature independently in complete isolation:
- Individual OS tools (`ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListFilesTool`, `ShellCommandTool`, `TimeTool`, `WeatherTool`, `WebSearchTool`, `FetchWebPageTool`, `OpenBrowserTool`, `WindowManagementTool`, `ScreenshotTool`, `SemanticSearchTool`, `DelegateTaskTool`).
- LLM Provider interfaces (OpenAI, Ollama, OpenRouter) and JSON function calling repair.
- `ConversationMemory` sliding window (`max_messages`) and on-change callback dispatch.
- REPL slash commands (`/clear`, `/help`, `/voice`, `/tools`, `/settings`).
- React pure memo components (`ChatMessageItem`, `ToolBlock`, `Sidebar`, `ArtifactRenderer`, `SettingsModal`, `WorkspaceSelector`, `AgentDashboard`, `VoicePanel`, `CreateProjectModal`).

### Tier 2: Boundary & Corner Cases
Tests system resilience under abnormal and extreme input boundaries:
- Rapid WebSocket streaming frames with malformed, binary, or unclosed JSON.
- Instant-send burst queues with out-of-order dispatch, repeated IDs, and empty payloads.
- Language switcher rapid toggle sequences (`en` -> `ru` -> `en` -> `ru`) and corrupted `localStorage`.
- Deeply nested i18n keys with numbers, empty strings, missing tokens, and special characters (`$100 & <script> \n`).
- Shell command execution with zero timeout, invalid working directories, and binary stdio outputs.

### Tier 3: Cross-Feature Pairwise Interactions
Validates state propagation across multiple subsystem boundaries:
- **Voice -> LLM -> Tool -> Audio TTS**: Audio input triggers speech recognition, dispatches to LLM with tool schemas, executes OS tool, formats output, and synthesizes speech (mocked during tests).
- **Workspace Switch -> Memory Persistence -> Settings Reload**: Switching workspace directory updates active project memory, persists conversation history to disk, and triggers configuration hot-reload without restarting server.
- **Instant Send -> Queue Dequeue -> WebSocket Stream**: Interleaved manual instant-send messages bypass queue while automatic sequential queue processing proceeds without deadlock.

### Tier 4: Real-World Application Workloads
Simulates end-to-end multi-turn developer scenarios:
- Multi-step software refactoring workflows (listing files, reading source code, applying line-bounded edits, executing compiler/test commands).
- Swarm sub-agent delegation workflows (spawning sub-agent, sharing isolated workspace context, returning consolidated report).
- Live chat lifecycle management (creating 10+ concurrent chats, renaming with polymorphic payloads, switching active context, deleting chats).

### Tier 5: Concurrency, Lifespan Shutdown & Zombie Process Elimination
Exercises high-concurrency stress and graceful process lifecycle termination:
- **Permission Lock 20-Thread Race**: 20 concurrent threads requesting permission simultaneously over WebSocket without deadlock or corrupted responses.
- **FastAPI Lifespan Teardown**: Server startup and shutdown sequence stops `WakeWordDetector`, quits `pygame.mixer`, shuts down all background MCP client processes, and releases runtime port.
- **Process Tree Cleanup on Windows**: Subprocesses spawned by `CommandExecutor` and `ShellCommandTool` are tracked in Job Objects and terminated cleanly on timeout or shutdown.
- **Zero Orphaned `python.exe` Guarantee**: All daemon threads and child worker processes terminate cleanly upon test completion.

---

## 5. Quality Gates & Verified Results

| Metric / Pipeline | Target Threshold | Actual Verification Result | Quality Gate Status |
|-------------------|------------------|----------------------------|---------------------|
| `pytest` Total Pass Rate | 100% | 439 / 439 Passed in 44s | **PASS** |
| `tests/test_frontend_stress.ts` | 80 / 80 Passed | 80 / 80 Passed (100%) | **PASS** |
| `tests/test_challenger_m2_adversarial.ts` | 50 / 50 Passed | 50 / 50 Passed (100%) | **PASS** |
| `tests/test_m2_challenger_deep_stress.ts` | 68 / 68 Passed | 68 / 68 Passed (100%) | **PASS** |
| `src/ui/verify_i18n_comprehensive.mjs` | 1302 / 1302 Passed | 1302 / 1302 Passed (100%) | **PASS** |
| `ruff check .` Lint Violations | 0 Errors | 0 Errors across all files | **PASS** |
| `mypy src tests` Type Violations | 0 Errors | 0 Errors across 93 files | **PASS** |
| Audio / TTS Suppression | 100% Silent | All TTS mocked & silenced | **PASS** |
| Frontend `npm run build` | Clean dist | Built in 2.09s | **PASS** |
| Frontend `npx tsc --noEmit` | Clean typecheck | 0 Type errors | **PASS** |
| Frontend `npm run lint` (oxlint) | 0 Errors | 0 Errors across 18 files | **PASS** |
| Untranslated Cyrillic in UI Components | 0 Found | 0 Found | **PASS** |
| Orphaned Child Processes | 0 Residual | 0 Residual Procs | **PASS** |

---

## 6. Complete Test Invocation Guide

### Running Python Pytest Suite
```powershell
# Run entire test suite (TTS automatically suppressed)
pytest

# Run with verbose output
pytest -v

# Run targeted E2E and Concurrency suites
pytest tests/test_e2e_friday.py tests/test_concurrency_stress.py tests/test_adversarial_m3.py tests/test_empirical_challenger_m1.py -v
```

### Running Static Type & Lint Quality Gates
```powershell
# Check linting across entire project
ruff check .

# Check strict type annotations across src and tests
mypy src tests
```

### Running Frontend Validation Suites
```powershell
# Run TypeScript Instant-Send & i18n stress tests (80 checks)
npx tsx tests/test_frontend_stress.ts

# Run Challenger M2 Adversarial test suite (50 checks)
npx tsx tests/test_challenger_m2_adversarial.ts

# Run Deep Stress Streaming & Memoization suite (68 checks)
npx tsx tests/test_m2_challenger_deep_stress.ts

# Run Comprehensive i18n 1302-check dictionary & UI audit
node src/ui/verify_i18n_comprehensive.mjs

# Build frontend production bundle
cd src/ui
npm run build

# Run frontend typecheck and oxlint
npx tsc --noEmit
npm run lint
```
