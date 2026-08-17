# Friday Strategic Development Plan (Stages 5-10)

After analyzing the current foundation (LLM, Memory, Task Planner, Terminal, Voice), we have outlined the global steps that transform Friday from just a "smart console chatbot" into a **fully autonomous OS AI agent**.

---

## 🧩 Stage 5: Plugin System and MCP (Model Context Protocol) ✅ Done

**Core idea:** Teach Friday to use third-party tools without modifying the core source code.
**Implemented:**
1. **MCP Support (Model Context Protocol)** — integrations that run as isolated servers.
2. **Plugin Manager (`src/plugins`)** — dynamic module loading.
3. **Permissions System** — security and access control.

---

## 👁️ Stage 6: Spatial Perception (Vision + RAG) ✅ Done

**Core idea:** Give Friday "eyes" and the ability to instantly navigate huge amounts of data.
**Implemented:**
1. **Vision Subsystem (`src/vision`)** — creating and analyzing screenshots.
2. **Semantic Search / RAG (`src/retrieval`)** — local index database (ChromaDB) for finding context across the project.

---

## 🤖 Stage 7: Background Daemon and Events (Proactive Agent) ✅ Done

**Core idea:** Untie Friday from the console and teach it to take initiative.
**Implemented:**
1. **Background Service (Daemon)** — Friday runs in the system tray, consuming minimal resources.
2. **Event Architecture (`src/daemon`)** — reacting to file system triggers and global hotkeys.

---

## 🖥️ Stage 8: Native Desktop Application (GUI) ✅ Done

**Core idea:** Create a convenient, standalone graphical application for users.
**Implemented:**
1. **FastAPI Backend (`src/api`)** — HTTP/WebSocket server acting as an autonomous engine (Sidecar).
2. **Vite + React + Tauri Frontend (`src/ui`)** — beautiful native desktop app with a Glassmorphism UI.
3. **In-App Settings and Configuration** — settings modal (`config.json`) with instant application (Hot-Reloading) without restarting the program.

---

## 🚀 Stage 9: Global Expansion and Integrations (PLANNED)

**Core idea:** Building up the agent's "muscles" to perform complex tasks and integrations with other services (setting up a very large and heavy task).
**Plans will be refined after the current sprint is completed and new requirements are received.**

---

## 🛡️ Stage 10: Global Fault-Tolerance and Offline Agents ✅ Done

**Core idea:** Make the agent bulletproof against network and format errors, and ensure full autonomy without an internet connection.
**Implemented:**
1. **Fault-Tolerance:** Automatic retries on network drops, a stateful parser for repairing broken LLM JSON, and protection against encoding crashes (Unicode).
2. **Ollama Native Tool Calling:** Local models can now natively call tools (similar to OpenAI), making Friday a fully autonomous offline assistant.
