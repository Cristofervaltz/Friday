"""Tests for the Task Planner subsystem."""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.llm.base import BaseLLMProvider, LLMResponse
from src.planner.executor import PlanExecutor
from src.planner.models import Plan, Task
from src.planner.planner import TaskPlanner


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider for testing planner generation."""

    def __init__(self, response_tool_calls: list[dict[str, Any]] | None = None) -> None:
        self.response_tool_calls = response_tool_calls

    def generate(self, prompt: str) -> str:
        return "mock response"

    def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        return LLMResponse(tool_calls=self.response_tool_calls)

    def model_name(self) -> str:
        return "mock-planner-llm"


class MockAgent:
    """Mock Agent for testing plan execution."""

    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.cleared = False
        self.run_calls: list[str] = []

    def clear_history(self) -> None:
        self.cleared = True

    def run(self, prompt: str) -> str:
        self.run_calls.append(prompt)
        if not self.success:
            raise RuntimeError("Agent execution failed")
        return "Task completed successfully"


def test_task_state_transitions() -> None:
    """Test Task dataclass state methods."""
    task = Task(description="Do something", expected_outcome="Done")
    assert task.status == "pending"
    assert task.result is None

    task.mark_in_progress()
    assert task.status == "in_progress"

    task.mark_completed(result="Success!")
    assert task.status == "completed"
    assert task.result == "Success!"

    task.mark_failed("Failed miserably")
    assert task.status == "failed"
    assert task.result == "Failed miserably"


def test_plan_properties() -> None:
    """Test Plan properties and serialization."""
    t1 = Task(description="Task 1", expected_outcome="T1 done")
    t2 = Task(description="Task 2", expected_outcome="T2 done")
    plan = Plan(goal="Overall goal", tasks=[t1, t2])

    assert plan.is_completed is False
    assert plan.has_failed is False
    assert plan.next_pending_task == t1

    t1.mark_completed("Done")
    assert plan.is_completed is False
    assert plan.next_pending_task == t2

    t2.mark_failed("Error")
    assert plan.has_failed is True
    assert plan.is_completed is False

    # Test JSON serialization
    json_str = plan.to_json()
    assert "Task 1" in json_str
    assert "Error" in json_str

    # Test deserialization
    plan2 = Plan.from_json(json_str)
    assert plan2.goal == plan.goal
    assert len(plan2.tasks) == 2
    assert plan2.tasks[0].status == "completed"
    assert plan2.tasks[1].status == "failed"


def test_task_planner_generate_plan() -> None:
    """Test TaskPlanner generating a plan via LLM."""
    mock_tasks = [
        {"description": "Step 1", "expected_outcome": "Outcome 1"},
        {"description": "Step 2", "expected_outcome": "Outcome 2"},
    ]
    mock_calls = [
        {
            "name": "create_plan",
            "arguments": json.dumps({"tasks": mock_tasks}),
        }
    ]
    mock_llm = MockLLMProvider(response_tool_calls=mock_calls)
    planner = TaskPlanner(mock_llm)

    plan = planner.generate_plan("Test goal")
    assert plan.goal == "Test goal"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].description == "Step 1"
    assert plan.tasks[1].expected_outcome == "Outcome 2"


def test_task_planner_missing_tool() -> None:
    """Test TaskPlanner when LLM fails to call create_plan."""
    mock_llm = MockLLMProvider(response_tool_calls=[{"name": "other_tool"}])
    planner = TaskPlanner(mock_llm)

    with pytest.raises(RuntimeError, match="missing 'create_plan'"):
        planner.generate_plan("Test goal")


def test_plan_executor_success() -> None:
    """Test PlanExecutor successfully executing a plan."""
    agent = MockAgent(success=True)
    executor = PlanExecutor(agent)  # type: ignore[arg-type]

    t1 = Task(description="Step 1", expected_outcome="1")
    t2 = Task(description="Step 2", expected_outcome="2")
    plan = Plan(goal="Goal", tasks=[t1, t2])

    success = executor.execute_plan(plan)
    assert success is True
    assert plan.is_completed is True
    assert len(agent.run_calls) == 2
    assert agent.cleared is True
    assert "Step 1" in agent.run_calls[0]
    assert "Step 2" in agent.run_calls[1]


def test_plan_executor_failure() -> None:
    """Test PlanExecutor stopping when a task fails."""
    agent = MockAgent(success=False)
    executor = PlanExecutor(agent)  # type: ignore[arg-type]

    t1 = Task(description="Step 1", expected_outcome="1")
    t2 = Task(description="Step 2", expected_outcome="2")
    plan = Plan(goal="Goal", tasks=[t1, t2])

    success = executor.execute_plan(plan)
    assert success is False
    assert plan.has_failed is True
    assert plan.is_completed is False
    assert t1.status == "failed"
    assert t2.status == "pending"
    assert len(agent.run_calls) == 1
