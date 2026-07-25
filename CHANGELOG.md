# Changelog

All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog*, and this project follows semantic versioning principles as it matures.

## [0.7.0] - 2026-07-25
### Added
- Proactive Background Daemon (`src.daemon` module) enabling zero-GUI background execution.
- System-wide global hotkey integration (`pynput`) triggered via `Ctrl+Alt+Space` to instantly launch voice tasks.
- File-based trigger monitoring (`watchdog`) in `~/.friday/triggers/` for background task spawning.
- System tray integration (`pystray`) for background daemon visibility.
- Headless execution flags (`--voice-task` and `--task`) in CLI to bridge the lightweight daemon with the AI core.

## [0.6.0] - 2026-07-25

### Added (Stage 6: Spatial Perception)
- **Vision Subsystem** — ability to take desktop screenshots for contextual debugging (`ScreenshotTool`)
- **RAG Subsystem** — local `ChromaDB` vector database with `all-MiniLM-L6-v2` embeddings for fast semantic code search (`SemanticSearchTool`)
- **Code Indexer** — automatic chunking and indexing of local workspace files (`CodeIndexer`)

## [0.5.0] - 2026-07-24

### Added (Stage 5: Extensibility & Voice)
- **Speech Subsystem** — high-quality voice command recognition via `/voice` using Google Web Speech API
- **MCP (Model Context Protocol)** — secure plugin architecture for connecting external tools dynamically

## [0.4.0] - 2026-07-23

### Added (Stage 4: Autonomy & Planning)
- **Task Planner Subsystem** — implemented multi-step goal decomposition (`TaskPlanner`)
- **Plan Executor** — sequentially runs agent tasks with safety halting on failure (`PlanExecutor`)
- **REPL `/plan` command** — generate and execute multi-step plans interactively

## [0.3.0] - 2026-07-23

### Added (Stage 3: Memory and Context)
- **Conversation Memory** — implemented short-term sliding window context (`ConversationMemory`)
- **Workspace Memory** — implemented persistent JSON storage for global context (`WorkspaceMemory`)
- Integrated memory subsystems into `Agent` core

## [0.2.0] - 2026-07-23

### Added (Stage 2: Interactive Core)
- **Command Execution Subsystem** — safe execution with timeouts and output limiting (`CommandExecutor`)
- **Shell Command Tool** — integrated terminal access for the Friday Agent (`ShellCommandTool`)
- Interactive agent tool-calling loop with REPL integration

## [0.1.0] - 2026-07-13

### Added (Stage 1: Foundation)
- **Runtime Core** — centralized application lifecycle manager (`FridayApplication`)
- **LLM Provider abstraction** — unified interface for language model providers
- **OpenAI, OpenRouter, Ollama providers** — support for frontier and local models
- **Working examples** — practical examples in `examples/` directory for all providers
- Python 3.12+ project configuration through `pyproject.toml`
- Centralized application configuration with dataclasses
- Reusable logging subsystem with console and rotating file handlers
- Comprehensive test suite covering configuration, logging, runtime, and all LLM providers
- Quality tooling with Black, Ruff, MyPy, and Pytest
- GitHub Actions CI workflow for validation on pushes and pull requests

### Changed
- `main.py` simplified to minimal entry point
- Application state now managed through Runtime Core

### Notes
- Version `0.1.0` is a foundation release focused on architecture, testing discipline, and extensible LLM integration
