<div align="center">

# 🗺️ Roadmap: Friday's Path to v1.0

This document outlines the evolutionary path of Friday, transitioning from a basic console script into a fully autonomous AI desktop assistant. Each major developmental stage corresponds to a minor version release.

</div>

---

## ✅ Completed Stages

### Stage 1: Foundation (`v0.1.0`)
- [x] **Project Architecture:** Implemented strict typing, linting (Black, Ruff, MyPy).
- [x] **LLM Abstraction Layer:** Unified support for multiple providers (OpenAI, OpenRouter, Ollama).
- [x] **Ollama Tool Calling:** Native support for local model function calling.

### Stage 2: Interactive Core (`v0.2.0`)
- [x] **Basic Terminal Interface:** Interactive REPL setup.
- [x] **Command Execution:** Safe execution of bash/shell commands with output limits.

### Stage 3: Memory and Context (`v0.3.0`)
- [x] **Conversation Memory:** Preserving dialogue history natively.
- [x] **Workspace Memory:** Indexing and understanding the structure of the local project directory.

### Stage 4: Autonomy & Planning (`v0.4.0`)
- [x] **Task Planner:** Autonomous agent capability to plan complex, multi-step tasks.
- [x] **Execution Engine:** Safe execution of planned steps with error recovery.
- [x] **Fault-Tolerance:** Advanced JSON parsing recovery, network retries, and unicode safety.

### Stage 5: Extensibility & Voice (`v0.5.0`)
- [x] **Speech Subsystem:** High-quality voice command recognition via `/voice`.
- [x] **MCP (Model Context Protocol):** Secure plugin architecture for connecting external tools without hardcoding them.

### Stage 6: Spatial Perception (`v0.6.0`)
- [x] **Vision Tool:** Added capability for the AI to "see" your screen (taking screenshots) to debug UIs and understand context visually.
- [x] **Semantic RAG Search:** Local vector database (`ChromaDB`) and local embeddings (`sentence-transformers`) for incredibly fast code search across large repositories.

---

## 🚀 Upcoming Stages

### Stage 7: Proactive Background Daemon (`v0.7.0`)
> **Goal:** Untie Friday from the console and teach it to take initiative in the background.

- [x] **Daemon Process:** Isolate a background service running in the Windows/Mac System Tray.
- [x] **Event Subsystem:** React to file triggers (e.g., code modifications) and schedules (cron jobs) proactively.
- [x] **Global Shortcut:** Summon Friday as an overlay on top of all windows via a global hotkey (Spotlight/Raycast style).

### Stage 8: Desktop GUI & Visual Interaction (`v0.8.0`)
> **Goal:** Provide a beautiful, interactive visual interface.

- [x] **Interactive Dashboard:** Web or native UI to display the agent's current thoughts, task plans, and background processes.
- [x] **Visual Permissions Management:** Aesthetic pop-ups for users to grant or deny sensitive actions.
- [x] **Artifacts Viewer:** View generated diagrams, code diffs, and images natively within the app.

### Stage 9: Cloud Sync & Self-Improvement (`v0.9.0`)
> **Goal:** Scale Friday beyond a single machine and enable self-reflection.

- [ ] **Cloud Context Sync:** Synchronize memory and workspace context securely across multiple devices.
- [x] **Agent Swarms:** Allow multiple Friday instances to collaborate on team projects.
- [ ] **Self-Improvement Mechanisms:** Enable the agent to analyze past failures, update its own system prompts, and write new local tools.

---

## 🏆 v1.0.0 — First Stable Release
Launch of a fully-featured, secure, and beautiful desktop companion, ready for daily production use by developers worldwide.
