"""Data models for the Friday Task Planner."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    """Represents a single step in a multi-step execution plan."""

    description: str
    expected_outcome: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "pending"  # pending, in_progress, completed, failed
    result: str | None = None

    def mark_in_progress(self) -> None:
        """Mark task as currently executing."""
        self.status = "in_progress"

    def mark_completed(self, result: str | None = None) -> None:
        """Mark task as successfully completed."""
        self.status = "completed"
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = "failed"
        self.result = error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "status": self.status,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create a Task instance from a dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            description=data["description"],
            expected_outcome=data["expected_outcome"],
            status=data.get("status", "pending"),
            result=data.get("result"),
        )


@dataclass
class Plan:
    """Represents a sequence of tasks to achieve a specific goal."""

    goal: str
    tasks: list[Task] = field(default_factory=list)

    @property
    def is_completed(self) -> bool:
        """Check if all tasks in the plan are completed."""
        return bool(self.tasks) and all(t.status == "completed" for t in self.tasks)

    @property
    def has_failed(self) -> bool:
        """Check if any task in the plan has failed."""
        return any(t.status == "failed" for t in self.tasks)

    @property
    def next_pending_task(self) -> Task | None:
        """Get the next task that hasn't been started yet."""
        for task in self.tasks:
            if task.status == "pending":
                return task
        return None

    def format_status(self) -> str:
        """Format the current status of the plan as a string."""
        lines = [f"Goal: {self.goal}", "Tasks:"]
        for i, task in enumerate(self.tasks, 1):
            if task.status == "completed":
                icon = "✅"
            elif task.status == "failed":
                icon = "❌"
            elif task.status == "in_progress":
                icon = "⏳"
            else:
                icon = "⬜"

            lines.append(f"  {i}. {icon} [{task.status}] {task.description}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize plan to JSON string."""
        data = {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Plan:
        """Create a Plan instance from JSON string."""
        data = json.loads(json_str)
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return cls(goal=data["goal"], tasks=tasks)
