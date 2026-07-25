<div align="center">

# 🗺️ Roadmap: Friday's Path to v1.0

This document describes how the project evolves from a basic console script into an autonomous AI assistant for your operating system.

</div>

---

## ✅ Completed Stages

### v0.0.1 - v0.1 — Foundation
* [x] Setup project architecture, linters (Black, Ruff, MyPy).
* [x] LLM provider abstraction (OpenAI, OpenRouter, Ollama).
* [x] Basic terminal interface (REPL).

### v0.2 — Memory and Context
* [x] `Conversation Memory` — preserving dialogue history.
* [x] `Workspace Memory` — indexing and remembering the structure of the project (user files).

### v0.3 — Executor and Extensibility
* [x] `Task Planner` — planning complex multi-step tasks.
* [x] `Execution Engine` — safe execution of planned steps.
* [x] `Speech Subsystem` — voice command recognition.
* [x] `MCP (Model Context Protocol)` — secure plugin architecture for connecting external tools.

---

## 🚀 Upcoming Global Stages

### Stage 6: Spatial Perception (Vision & RAG)
**Goal:** Give Friday "eyes" and the ability to instantly navigate massive amounts of data.
* [ ] Integration of `vision` tools for reading screenshots.
* [ ] Local vector database (`ChromaDB`) for semantic RAG search across the project code.
* [ ] Ability for the AI to understand the context of huge repositories on the fly, without overflowing the context window.

### Stage 7: Background Daemon and Events (Proactive Agent)
**Goal:** Untie Friday from the console and teach it to take initiative in the background.
* [ ] Isolation of a background service (Daemon) running in the Windows/Mac System Tray.
* [ ] Event subsystem (`src/events/`) for reacting to file triggers (e.g., code changes) and schedules (cron jobs).
* [ ] Summon Friday on top of all windows via a global hotkey (Spotlight/Raycast style).

### Stage 8: UI and Interaction
**Goal:** A convenient visual interface instead of a dry console.
* [ ] Interactive web dashboards for displaying the agent's thoughts, plans, and current background tasks.
* [ ] Visual permission management (when the agent asks to confirm file deletion).

## 🏆 v1.0 — First Stable Release
Launch of a fully-featured, secure, and beautiful desktop companion, ready for daily production use by developers.
