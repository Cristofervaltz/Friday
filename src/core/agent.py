"""AI Agent with function calling and memory capabilities."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from src.constants import APP_NAME
from src.logger import LoggerFactory
from src.memory.conversation import ConversationMemory
from src.utils.json_repair import repair_json

if TYPE_CHECKING:
    from src.core.tool_registry import ToolRegistry
    from src.llm.base import BaseLLMProvider, LLMResponse


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
        llm_provider: BaseLLMProvider | None,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
        memory: ConversationMemory | None = None,
        cancel_event: Any = None,
    ) -> None:
        """Initialize the agent.

        Args:
            llm_provider: LLM provider for generating responses.
            tool_registry: Registry of available tools.
            max_iterations: Maximum number of tool calling iterations.
            memory: Optional custom ConversationMemory instance.
            cancel_event: Optional threading.Event to abort execution.
        """
        self.llm = llm_provider
        self.tools = tool_registry
        self.max_iterations = max_iterations
        self.memory = memory if memory is not None else ConversationMemory()
        self.cancel_event = cancel_event
        self._logger = _get_logger("core.agent")

    def run(self, user_input: str | None = None) -> str:
        """Process user input and return agent's response.

        Args:
            user_input: User's message/request, or None to just continue generation.

        Returns:
            Agent's final response after tool execution (if any),
            or a graceful error message on failure.

        Raises:
            RuntimeError: If max iterations exceeded (infinite loop).
        """
        if user_input is not None:
            self.memory.add_user_message(user_input)

        if self.llm is None:
            msg = "⚠️ Не настроена нейросеть. Пожалуйста, откройте настройки (иконка шестеренки) и укажите ваш API ключ."
            self.memory.add_assistant_message(content=msg)
            return msg

        tools_schema = self.tools.get_tools_schema()

        iteration = 0
        while iteration < self.max_iterations:
            if self.cancel_event and self.cancel_event.is_set():
                msg = "🛑 Выполнение прервано пользователем."
                self.memory.add_assistant_message(content=msg)
                return msg

            iteration += 1

            messages = self.memory.get_messages()
            
            max_retries = 3
            retry_count = 0
            response: LLMResponse | None = None
            
            while retry_count <= max_retries:
                try:
                    response = self.llm.generate_with_tools(
                        messages=messages,
                        tools=tools_schema,
                    )
                    break
                except Exception as exc:
                    error_str = str(exc).lower()
                    if "503" in error_str or "502" in error_str or "500" in error_str or "429" in error_str or "server_error" in error_str or "rate_limit" in error_str or "busy" in error_str:
                        if retry_count < max_retries:
                            self._logger.warning("LLM API error (503/429/500). Retrying %d/%d in %d seconds...", retry_count + 1, max_retries, 2 ** retry_count)
                            time.sleep(2 ** retry_count)
                            retry_count += 1
                            continue
                        else:
                            self._logger.exception("LLM generation failed after %d retries: %s", max_retries, exc)
                            error_msg = f"❌ Error communicating with LLM: {exc}"
                            self.memory.add_assistant_message(content=error_msg)
                            return error_msg
                    else:
                        self._logger.exception("LLM generation failed: %s", exc)
                        error_msg = f"❌ Error communicating with LLM: {exc}"
                        self.memory.add_assistant_message(content=error_msg)
                        return error_msg

            if response is None:
                error_msg = "❌ Error communicating with LLM: No response received"
                self.memory.add_assistant_message(content=error_msg)
                return error_msg

            if response.tool_calls:
                formatted_calls = []
                parsed_tool_calls = []

                for idx, tool_call in enumerate(response.tool_calls):
                    if not isinstance(tool_call, dict):
                        continue
                    call_id = tool_call.get("id") or f"call_{idx + 1}"
                    name = tool_call.get("name") or "unknown_tool"
                    raw_args = tool_call.get("arguments", {})
                    parse_error = None
                    parsed_args: dict[str, Any] = {}

                    if isinstance(raw_args, str):
                        try:
                            repaired = repair_json(raw_args)
                            if isinstance(repaired, dict):
                                parsed_args = repaired
                            else:
                                parsed_args = {}
                        except Exception as exc:
                            parse_error = str(exc)
                            parsed_args = {}
                    elif isinstance(raw_args, dict):
                        parsed_args = raw_args

                    tool_call["id"] = call_id
                    tool_call["name"] = name
                    tool_call["arguments"] = parsed_args
                    parsed_tool_calls.append((tool_call, raw_args, parse_error))

                    fn_dict: dict[str, Any] = {
                        "name": name,
                        "arguments": json.dumps(
                            parsed_args,
                            ensure_ascii=False,
                        ),
                    }
                    
                    # Preserve extra fields like thought_signature
                    for k, v in tool_call.items():
                        if k not in ["id", "type", "name", "arguments"]:
                            fn_dict[k] = v

                    formatted_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": fn_dict,
                        }
                    )

                self.memory.add_assistant_message(
                    content=None, tool_calls=formatted_calls
                )

                for tool_call, raw_args, parse_error in parsed_tool_calls:
                    call_id = tool_call["id"]
                    name = tool_call["name"]
                    arguments = tool_call["arguments"]

                    if parse_error is not None:
                        result_content = f"Error: Failed to parse tool arguments from model: {raw_args}"
                    else:
                        try:
                            context = getattr(self.tools, "context", None)
                            if context is not None:
                                previous_agent = getattr(context, "agent", None)
                                context.agent = self
                                try:
                                    tool_result = self.tools.execute(
                                        name,
                                        **arguments,
                                    )
                                finally:
                                    context.agent = previous_agent
                            else:
                                tool_result = self.tools.execute(
                                    name,
                                    **arguments,
                                )

                            if tool_result.success:
                                result_content = (
                                    str(tool_result.output)
                                    if tool_result.output is not None
                                    else "Tool executed successfully."
                                )
                            else:
                                result_content = f"Error: {tool_result.error if tool_result.error is not None else 'Unknown tool error'}"
                        except Exception as exc:
                            result_content = f"Error executing tool: {exc}"

                    self.memory.add_tool_result(
                        tool_call_id=call_id,
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


def _get_logger(name: str) -> logging.Logger:
    """Return Friday's configured logger when available, otherwise a safe fallback."""
    try:
        return LoggerFactory().get_logger(name)
    except RuntimeError:
        return logging.getLogger(f"{APP_NAME}.{name}")
