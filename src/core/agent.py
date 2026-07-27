"""AI Agent with function calling and memory capabilities."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.memory.conversation import ConversationMemory

if TYPE_CHECKING:
    from src.core.tool_registry import ToolRegistry
    from src.llm.base import BaseLLMProvider


class Agent:
    """AI Agent that orchestrates conversation, tool usage, and memory.

    Handles the function calling execution loop:
    1. User sends message
    2. LLM decides which tool to call (if any)
    3. Agent executes the tool
    4. Result goes back to LLM
    5. Repeat until LLM provides final answer
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
        memory: ConversationMemory | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            llm_provider: LLM provider for generating responses.
            tool_registry: Registry of available tools.
            max_iterations: Maximum number of tool calling iterations.
            memory: Optional custom ConversationMemory instance.
        """
        self.llm = llm_provider
        self.tools = tool_registry
        self.max_iterations = max_iterations
        self.memory = memory if memory is not None else ConversationMemory()

    def run(self, user_input: str) -> str:
        """Process user input and return agent's response.

        Args:
            user_input: User's message/request.

        Returns:
            Agent's final response after tool execution (if any).

        Raises:
            RuntimeError: If max iterations exceeded (infinite loop).
        """
        self.memory.add_user_message(user_input)

        tools_schema = self.tools.get_tools_schema()

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            messages = self.memory.get_messages()
            response = self.llm.generate_with_tools(
                messages=messages,
                tools=tools_schema,
            )

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    try:
                        tool_result = self.tools.execute(
                            tool_call["name"],
                            **tool_call["arguments"],
                        )
                        if tool_result.success:
                            result_content = (
                                tool_result.output
                                if tool_result.output is not None
                                else "Tool executed successfully."
                            )
                        else:
                            result_content = (
                                f"Error: {tool_result.error or 'Unknown tool error'}"
                            )
                    except Exception as exc:
                        result_content = f"Error executing tool: {exc}"

                    formatted_calls = [
                        {
                            "id": tool_call.get("id", "call_1"),
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": json.dumps(tool_call["arguments"]),
                            },
                        }
                    ]
                    self.memory.add_assistant_message(
                        content=None, tool_calls=formatted_calls
                    )
                    self.memory.add_tool_result(
                        tool_call_id=tool_call.get("id", "call_1"),
                        content=result_content,
                    )

                continue

            else:
                final_response = response.content or ""
                self.memory.add_assistant_message(content=final_response)
                return final_response

        raise RuntimeError(
            f"Agent exceeded max iterations ({self.max_iterations}). "
            "Possible infinite loop."
        )

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.memory.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Get conversation history.

        Returns:
            List of conversation messages.
        """
        return self.memory.get_messages()
