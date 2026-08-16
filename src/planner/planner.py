"""Task Planner for decomposing complex goals into sequential steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.planner.models import Plan, Task
from src.utils.json_repair import repair_json

if TYPE_CHECKING:
    from src.llm.base import BaseLLMProvider


class TaskPlanner:
    """Decomposes a goal into a structured multi-step execution plan."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        """Initialize the TaskPlanner.

        Args:
            llm_provider: The LLM provider to use for planning.
        """
        self.llm = llm_provider

    def generate_plan(self, goal: str) -> Plan:
        """Generate an execution plan for a given goal.

        Args:
            goal: The overarching user goal or prompt.

        Returns:
            A Plan instance containing the sequential tasks.

        Raises:
            RuntimeError: If the LLM fails to generate a valid plan.
        """
        system_prompt = (
            "You are an expert technical planner. "
            "Your job is to break down the user's complex goal into a sequence of "
            "small, actionable, and testable tasks. "
            "You MUST call the 'create_plan' function to output your plan."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": goal},
        ]

        create_plan_schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": "create_plan",
                "description": "Submit the multi-step execution plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "description": "List of tasks in execution order.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {
                                        "type": "string",
                                        "description": "Clear description of the task.",
                                    },
                                    "expected_outcome": {
                                        "type": "string",
                                        "description": "How to verify success.",
                                    },
                                },
                                "required": ["description", "expected_outcome"],
                            },
                        }
                    },
                    "required": ["tasks"],
                },
            },
        }

        response = self.llm.generate_with_tools(
            messages=messages,
            tools=[create_plan_schema],
        )

        if not response.tool_calls:
            raise RuntimeError(
                "LLM failed to use the 'create_plan' tool. "
                f"Response was: {response.content}"
            )

        # Look for create_plan tool call
        for tool_call in response.tool_calls:
            if tool_call["name"] == "create_plan":
                args = tool_call.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = repair_json(args)
                    except Exception as exc:
                        raise RuntimeError("Failed to parse LLM tool call.") from exc

                if isinstance(args, dict):
                    raw_tasks = args.get("tasks", [])
                elif isinstance(args, list):
                    raw_tasks = args
                else:
                    raw_tasks = []

                tasks = []
                for t in raw_tasks:
                    if isinstance(t, dict):
                        tasks.append(
                            Task(
                                description=t.get("description", "Unknown task"),
                                expected_outcome=t.get("expected_outcome", ""),
                            )
                        )
                    elif isinstance(t, str):
                        tasks.append(Task(description=t, expected_outcome=""))

                return Plan(goal=goal, tasks=tasks)

        raise RuntimeError("LLM called tools, but missing 'create_plan'.")
