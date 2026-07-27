"""Tool for delegating tasks to sub-agents (Multi-Agent Swarm)."""

import uuid
from typing import Any

from src.core.agent import Agent
from src.memory.conversation import ConversationMemory
from src.tools.base import BaseTool, ToolResult


class DelegateTaskTool(BaseTool):
    """Tool that spins up an isolated sub-agent to perform a specific task."""

    name = "delegate_task"

    def __init__(self, app: Any, registry: Any) -> None:
        """Initialize the DelegateTaskTool.

        Args:
            app: The FridayApplication instance.
            registry: The ToolRegistry instance.
        """
        self.app = app
        self.registry = registry

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Delegate a complex task to a specialized sub-agent. The sub-agent "
            "will have its own isolated context and tools. Use this to break down "
            "large problems or to perform specialized research without cluttering "
            "your own context. Wait for it to finish and return its result."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "The specific role/profession for the sub-agent (e.g., 'Senior Python Dev', 'Web Researcher').",
                },
                "task": {
                    "type": "string",
                    "description": "The detailed instructions or task for the sub-agent to perform.",
                },
            },
            "required": ["role", "task"],
        }

    def execute(self, role: str, task: str) -> ToolResult:
        """Execute the sub-agent task.

        Args:
            role: The role for the sub-agent.
            task: The task for the sub-agent.

        Returns:
            ToolResult containing the sub-agent's final response.
        """
        try:
            # Generate a unique chat ID for the sub-agent
            sub_chat_id = f"sub_{uuid.uuid4().hex[:8]}"

            # Define the system prompt
            system_prompt = (
                f"You are a specialized sub-agent. Your role is: {role}.\n"
                f"Your specific task is: {task}\n"
                "You have access to local tools. You must use them to accomplish the task.\n"
                "When you are finished, output your final result clearly so the main agent can read it."
            )

            # Create a new isolated memory
            save_dir = (
                self.app.config.paths.data_dir / "chats" if self.app.config else None
            )
            memory = ConversationMemory(
                system_prompt=system_prompt,
                chat_id=sub_chat_id,
                save_dir=save_dir,
            )
            
            # The UI prefix for sub-agents (Vector icon will be handled by UI, but we use a text indicator)
            memory.title = f"[Sub-Agent] {role}"

            # Copy WebSocket callbacks from the main agent so the UI can stream updates live
            if hasattr(self.app, "repl") and getattr(self.app, "repl"):
                main_memory = self.app.repl._agent.memory
                for cb in main_memory._on_change_callbacks:
                    memory.add_on_change_callback(cb)
            
            # Trigger initial UI update so the chat appears in the sidebar immediately
            memory._trigger_on_change()

            # Instantiate the sub-agent
            sub_agent = Agent(
                llm_provider=self.app.provider,
                tool_registry=self.registry,
                memory=memory,
                max_iterations=self.app.config.llm.max_iterations if self.app.config else 10,
            )

            # Run the task sequentially
            final_response = sub_agent.run(task)

            return ToolResult(
                success=True,
                output=f"Sub-agent '{role}' completed the task. Response:\n{final_response}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Sub-agent failed: {str(e)}",
            )
