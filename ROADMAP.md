<div align="center">

# 🗺️ Roadmap: Friday's Path to v1.0

This document outlines the evolutionary path of Friday, transitioning from a basic console script into a fully autonomous AI desktop assistant.

</div>

---

## ✅ Completed Stages

### v0.0.1 - v0.1 — Foundation
- [x] **Project Architecture & Quality Standards:** Implemented strict typing, linting (Black, Ruff, MyPy).
- [x] **LLM Abstraction Layer:** Support for multiple providers (OpenAI, OpenRouter, Ollama).
- [x] **Basic Terminal Interface:** Interactive REPL.

### v0.2 — Memory and Context
- [x] **Conversation Memory:** Preserving dialogue history natively.
- [x] **Workspace Memory:** Indexing and understanding the structure of the local project directory.

### v0.3 — Executor and Extensibility
- [x] **Task Planner:** Autonomous agent capability to plan complex, multi-step tasks.
- [x] **Execution Engine:** Safe execution of planned steps with error recovery.
- [x] **Speech Subsystem:** High-quality voice command recognition via `/voice`.
- [x] **MCP (Model Context Protocol):** Secure plugin architecture for connecting external tools without hardcoding them.

### Stage 6: Spatial Perception (Vision & RAG)
- [x] **Vision Tool:** Added capability for the AI to "see" your screen (taking screenshots) to debug UIs and understand context visually.
- [x] **Semantic RAG Search:** Local vector database (`ChromaDB`) and local embeddings (`sentence-transformers`) for incredibly fast code search across large repositories.

---

## 🚀 Upcoming Global Stages

### Stage 7: Background Daemon and Events (Proactive Agent)
> **Goal:** Untie Friday from the console and teach it to take initiative in the background.

- [ ] **Daemon Process:** Isolate a background service running in the Windows/Mac System Tray.
- [ ] **Event Subsystem:** React to file triggers (e.g., code modifications) and schedules (cron jobs) proactively.
- [ ] **Global Shortcut:** Summon Friday as an overlay on top of all windows via a global hotkey (Spotlight/Raycast style).

### Stage 8: UI and Interaction (Desktop GUI)
> **Goal:** Provide a beautiful, interactive visual interface.

- [ ] **Interactive Dashboard:** Web or native UI to display the agent's current thoughts, task plans, and background processes.
- [ ] **Visual Permissions Management:** Aesthetic pop-ups for users to grant or deny sensitive actions (e.g., executing shell scripts, deleting files).
- [ ] **Artifacts Viewer:** View generated diagrams, code diffs, and images natively within the app.

---

## 🏆 v1.0 — First Stable Release
Launch of a fully-featured, secure, and beautiful desktop companion, ready for daily production use by developers worldwide.
