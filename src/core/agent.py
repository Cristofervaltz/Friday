"""AI Agent with function calling capabilities."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.tool_registry import ToolRegistry
    from src.llm.base import BaseLLMProvider


class Agent:
    """AI Agent that can use tools through function calling.

    The agent orchestrates the conversation between the user, LLM,
    and tools. It handles the function calling loop:
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
    ) -> None:
        """Initialize the agent.

        Args:
            llm_provider: LLM provider for generating responses.
            tool_registry: Registry of available tools.
            max_iterations: Maximum number of tool calling iterations
                           to prevent infinite loops.
        """
        self.llm = llm_provider
        self.tools = tool_registry
        self.max_iterations = max_iterations
        self._conversation_history: list[dict[str, Any]] = []

    def run(self, user_input: str) -> str:
        """Process user input and return agent's response.

        Args:
            user_input: User's message/request.

        Returns:
            Agent's final response after tool execution (if any).

        Raises:
            RuntimeError: If max iterations exceeded (infinite loop).
        """
        # Add user message to conversation
        self._conversation_history.append({"role": "user", "content": user_input})

        # Get tools schema for function calling
        tools_schema = self.tools.get_tools_schema()

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            # Generate response with tools
            response = self.llm.generate_with_tools(
                messages=self._conversation_history,
                tools=tools_schema,
            )

            # Check if LLM wants to call a function
            if response.tool_calls:
                # Process all tool calls
                for tool_call in response.tool_calls:
                    # Execute tool
                    try:
                        tool_result = self.tools.execute(
                            tool_call["name"],
                            **tool_call["arguments"],
                        )

                        # Format result for LLM
                        result_content = (
                            tool_result.output
                            if tool_result.success
                            else f"Error: {tool_result.error}"
                        )

                    except Exception as exc:
                        result_content = f"Error executing tool: {exc}"

                    # Add tool call and result to conversation
                    self._conversation_history.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.get("id", "call_1"),
                                    "type": "function",
                                    "function": {
                                        "name": tool_call["name"],
                                        "arguments": json.dumps(tool_call["arguments"]),
                                    },
                                }
                            ],
                        }
                    )

                    self._conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", "call_1"),
                            "content": result_content,
                        }
                    )

                # Continue loop to let LLM process tool results
                continue

            else:
                # No tool calls - LLM provided final answer
                final_response = response.content or ""
                self._conversation_history.append(
                    {"role": "assistant", "content": final_response}
                )
                return final_response

        # Max iterations exceeded
        raise RuntimeError(
            f"Agent exceeded max iterations ({self.max_iterations}). "
            "Possible infinite loop."
        )

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Get conversation history.

        Returns:
            List of conversation messages.
        """
        return self._conversation_history.copy()
