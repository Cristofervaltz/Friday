"""Tool for delegating tasks to sub-agents (Multi-Agent Swarm)."""

import uuid
from typing import Any

from src.core.agent import Agent
from src.memory.conversation import ConversationMemory
from src.tools.base import BaseTool, ToolResult


class DelegateTaskTool(BaseTool):
    """Tool that spins up an isolated sub-agent to perform a specific task."""

    @property
    def name(self) -> str:
        return "delegate_task"

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
    def parameters_schema(self) -> dict[str, Any]:
        """Return tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "Role/profession for the sub-agent.",
                },
                "task": {
                    "type": "string",
                    "description": "Detailed task for sub-agent.",
                },
            },
            "required": ["role", "task"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the sub-agent task.

        Args:
            **kwargs: Tool arguments from LLM. Expected 'role' and 'task'.

        Returns:
            ToolResult containing the sub-agent's final response.
        """
        role = kwargs.get("role")
        task = kwargs.get("task")

        if not role or not task:
            return ToolResult(
                success=False,
                error="Missing required parameters: 'role' and 'task'.",
            )

        try:
            # Generate a unique chat ID for the sub-agent
            sub_chat_id = f"sub_{uuid.uuid4().hex[:8]}"

            # Define the system prompt
            system_prompt = (
                f"You are a specialized sub-agent. Your role is: {role}.\n"
                f"Your specific task is: {task}\n"
                "Use local tools to accomplish the task.\n"
                "When finished, output final result clearly."
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

            # UI prefix for sub-agents
            memory.title = f"[Sub-Agent] {role}"

            # Copy WebSocket callbacks from main agent for UI live updates
            if hasattr(self.app, "repl") and self.app.repl:
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
                max_iterations=(
                    self.app.config.llm.max_iterations if self.app.config else 10
                ),
            )

            # Run the task sequentially
            final_response = sub_agent.run(task)

            return ToolResult(
                success=True,
                output=f"Sub-agent '{role}' done. Response:\n{final_response}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Sub-agent failed: {str(e)}",
            )
