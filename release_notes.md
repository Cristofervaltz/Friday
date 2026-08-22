### 🚀 Welcome to Friday v1.5.0 — The Skills & Stability Update!

We are thrilled to announce **Friday v1.5.0**, a major update that brings highly requested extensibility features, a significantly more polished user interface, and massive under-the-hood architectural improvements as we pave the way for version 2.0.

#### ✨ What's New in v1.5.0

* 🧠 **Native Custom Skills**
  You can now seamlessly extend Friday\'s capabilities using your own custom instructions! Simply drop a .md file into the ~/.friday/skills/ directory. These files automatically sync with the frontend and appear in the / slash-command menu (e.g., /reviewer, /architect). Triggering them instantly injects your tailored system instructions into the agent\'s context.
* ⚡ **Dynamic Action Button**
  The chat interface is now smarter and more intuitive. While Friday is actively generating a response or executing tools, the send button transforms into a minimalist **Stop** button, allowing you to instantly halt execution. If you begin typing a new thought while she is busy, it seamlessly shifts into a **Queue** button to queue up your next message.
* 🎨 **Refined Aesthetics**
  We have entirely purged hardcoded emojis from the application interface. Everything has been replaced with beautiful, crisp, and stylistically consistent **Lucide React** vector icons, delivering a much cleaner and professional user experience.
* 🐝 **Background Tasks & Swarm Foundations**
  We have made deep architectural improvements to background processing and agent delegation. This lays the critical groundwork for the autonomous multi-agent sessions coming in v2.0, while ensuring that the main UI remains flawlessly responsive even during complex, long-running agent workflows.
* 🛡️ **Ironclad Stability**
  This release addresses several core engine quirks. We resolved WebSocket disconnect edge cases, patched memory truncation logic, and fortified the backend with strict static typing (mypy, 
uff) and robust thread-safe locks for concurrent settings I/O.

#### 📦 Installation

1. Download the **Friday_1.5.0_x64_en-US.msi** or **.exe** setup file below.
2. Run the installer to upgrade your current version.
3. Open Friday and explore your new Custom Skills!

*As always, thank you for your incredible support! If you love using Friday, don\'t forget to leave a ⭐ on the GitHub repository!*