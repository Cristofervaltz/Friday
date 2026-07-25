<div align="center">

# 🤖 Friday
**The Next-Generation Local AI Assistant for Developers.**

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge)](https://github.com/psf/black)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue?style=for-the-badge)](https://mypy-lang.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](LICENSE)

*«Friday is not just a chatbot. It is a reliable, autonomous AI assistant living on your computer, deeply integrated with your local files, tools, and workflows.»*

<br/>

[Features](#-key-features) •
[Architecture](#-architecture) •
[Installation](#-installation) •
[Usage](#-usage) •
[Roadmap](#-roadmap)

</div>

---

## ✨ Key Features

Friday brings the power of agentic AI directly to your desktop, offering an unparalleled developer experience through a suite of advanced subsystems.

### 🧠 Autonomous Execution Engine
Friday doesn't just answer questions; it acts. The built-in **Task Planner** breaks down complex, ambiguous goals into actionable steps, executes them using local tools, and autonomously handles errors or unexpected behaviors along the way.

### 👁️ Vision & Context Awareness
Friday can see what you see. Using the `[vision]` subsystem, the assistant can take screenshots of your active monitors to understand visual context, debug UI issues, or analyze architecture diagrams.

### 🗣️ Voice Interaction
Type `/voice` and speak directly to Friday! Powered by advanced noise-filtering algorithms, the `[speech]` subsystem allows for hands-free, seamless communication during your workflow.

### 📚 RAG & Semantic Code Search
Never lose track of your codebase. Friday's `[rag]` subsystem uses a local `ChromaDB` vector database and `sentence-transformers` to index your workspace, allowing the AI to perform lightning-fast semantic searches across thousands of files.

### 🔌 MCP (Model Context Protocol) Support
Easily extend Friday's capabilities on the fly. Connect external databases, GitHub, Jira, or web search tools securely via MCP without altering the core source code.

### 💾 Persistent Dual-Memory
- **Conversation Memory:** Remembers the context of your current and past conversations.
- **Workspace Memory:** Maintains an understanding of your project's structure, tech stack, and conventions.

### 🔄 Flexible LLM Backends
Total freedom of choice. Run completely offline and free using local models via **Ollama**, or leverage state-of-the-art frontier models like `gpt-4o` and `claude-3.5-sonnet` via **OpenRouter** or direct API keys.

---

## 🏗️ Architecture

Friday is built on the principles of **reliability**, **modularity**, and **security**.

```mermaid
graph TD
    A[Terminal / Voice REPL] --> B(Friday Runtime)
    B --> C{Task Planner}
    C -->|Decompose| D[Execution Engine]
    D --> E[Tools Registry]
    
    subgraph Local Environment
    E --> F((Shell / Bash))
    E --> G((File System))
    E --> V((Vision Capture))
    E --> S((Semantic Search))
    end
    
    E -.-> H((MCP Plugins))
    
    D --> I[LLM Abstraction Layer]
    subgraph Providers
    I --> J[OpenRouter / OpenAI]
    I --> K[Ollama Local]
    end
    
    B --> L[(Memory / Context)]
```

> [!NOTE]  
> **Security First:** Friday operates within strict boundaries. Command execution and file system access are logged, and potentially destructive actions can be configured to require explicit user approval.

---

## 🚀 Installation

### Prerequisites
- **Python 3.12+**
- **Ollama** *(Optional: Only if you want to run local models)*

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Cristofervaltz/Friday.git
   cd Friday
   ```

2. **Create a virtual environment & install the core:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install --upgrade pip
   
   # Core installation
   pip install -e .
   ```

3. **Install optional subsystems (Recommended for full experience):**
   ```bash
   # Install Voice support
   pip install -e .[speech]
   
   # Install Vision (Screenshots) support
   pip install -e .[vision]
   
   # Install RAG (Semantic Search) support
   pip install -e .[rag]
   
   # Install GUI & Daemon support
   pip install -e .[gui,daemon]
   
   # Or install ALL features at once:
   pip install -e .[speech,vision,rag,gui,daemon]
   ```

### Configuration

Copy the example environment file and add your keys:

```bash
cp .env.example .env
```

<details>
<summary><b>🔧 Configure OpenRouter (GPT-4, Claude)</b></summary>

```env
FRIDAY_LLM_PROVIDER=openrouter
FRIDAY_LLM_API_KEY=sk-or-v1-...
FRIDAY_LLM_MODEL=openai/gpt-4o
```
</details>

<details>
<summary><b>🔧 Configure Ollama (Local, Free)</b></summary>

```env
FRIDAY_LLM_PROVIDER=ollama
FRIDAY_LLM_MODEL=llama3
FRIDAY_LLM_BASE_URL=http://localhost:11434
```
</details>

---

## 💻 Usage

### 1. Terminal Mode
Start the interactive REPL:

```bash
friday
```

Once inside the REPL, you can type your requests naturally, or use the following slash commands:

- `/voice` - Activate microphone and speak your request.
- `/clear` - Clear the current conversation context.
- `/exit` or `/quit` - Safely shut down Friday.

### 2. Daemon & Dashboard Mode
Run Friday in the background with a System Tray icon and a beautiful Web Dashboard:

```bash
friday-daemon
```

*Right-click the Friday icon in your system tray and select **Dashboard** to interact with the AI via a modern web interface!*

---

## 🗺️ Roadmap

Friday is actively evolving. We are currently implementing features across several major stages, including a background Daemon Mode, a Desktop GUI, and proactive CI/CD monitoring.

Check out our full detailed [Future Roadmap](future_roadmap.md) to see what's coming next!

---

## 🛠️ For Developers

Contributions are highly welcome! We maintain strict code quality standards to ensure a robust foundation.

```bash
# Install development dependencies
pip install -e .[dev,speech,vision,rag]

# Run the test suite
python -m pytest

# Check code formatting & linting
black .
ruff check .

# Check static typing
mypy src tests
```

> [!TIP]
> Ensure all GitHub Actions CI checks pass before submitting a Pull Request.

---

<div align="center">
  <p>Made with ❤️ by the Friday Contributors.</p>
  <p>Licensed under the <a href="LICENSE">MIT License</a>.</p>
</div>
