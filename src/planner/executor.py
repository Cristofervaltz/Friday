"""Plan Executor for coordinating agent actions according to a plan."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.agent import Agent
    from src.planner.models import Plan


logger = logging.getLogger("friday.planner")


class PlanExecutor:
    """Executes a multi-step plan using the Friday Agent."""

    def __init__(self, agent: Agent) -> None:
        """Initialize the PlanExecutor.

        Args:
            agent: The AI agent responsible for executing individual tasks.
        """
        self.agent = agent

    def execute_plan(self, plan: Plan) -> bool:
        """Execute all pending tasks in the plan sequentially.

        Args:
            plan: The Plan instance containing tasks.

        Returns:
            True if all tasks succeeded, False if any task failed.
        """
        logger.info(f"Starting execution of plan: {plan.goal}")

        while True:
            task = plan.next_pending_task
            if task is None:
                break

            logger.info(f"Executing task: {task.description}")
            task.mark_in_progress()

            # Construct task prompt
            prompt = (
                f"Your task: {task.description}\n"
                f"Expected outcome to verify success: {task.expected_outcome}\n\n"
                "Please execute this task using your tools, and respond with a "
                "summary of what you accomplished when finished."
            )

            try:
                # Clear agent history to maintain focused context for each task
                self.agent.clear_history()

                # Run the agent
                result_text = self.agent.run(prompt)

                task.mark_completed(result_text)
                logger.info(f"Task completed successfully: {task.id}")

            except Exception as exc:
                error_msg = f"Task failed during execution: {exc}"
                logger.error(error_msg)
                task.mark_failed(error_msg)
                return False

        is_success = plan.is_completed
        logger.info(f"Plan execution finished. Success: {is_success}")
        return is_success
