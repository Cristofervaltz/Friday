"""Interactive REPL for Friday."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core import Agent, ToolRegistry
from src.planner import PlanExecutor, TaskPlanner
from src.tools import (
    EditFileTool,
    ListFilesTool,
    ReadFileTool,
    ShellCommandTool,
    WriteFileTool,
)

if TYPE_CHECKING:
    from src.runtime import FridayApplication


class FridayREPL:
    """Interactive Read-Eval-Print Loop for Friday.

    Provides a simple command-line interface for conversing with Friday
    through the configured LLM provider.
    """

    def __init__(self, app: FridayApplication) -> None:
        """Initialize the REPL with a Friday application instance.

        Args:
            app: Initialized FridayApplication with LLM provider.
        """
        self._app = app
        self._running = False

        # Initialize tool registry
        self._registry = ToolRegistry()
        self._registry.register(ReadFileTool())
        self._registry.register(WriteFileTool())
        self._registry.register(EditFileTool())
        self._registry.register(ListFilesTool())
        self._registry.register(ShellCommandTool())

        # Initialize agent with tools
        self._agent = Agent(
            llm_provider=app.provider,
            tool_registry=self._registry,
            max_iterations=10,
        )

        # Keep manual tools for direct commands
        self._tools = {
            "read": ReadFileTool(),
            "write": WriteFileTool(),
            "edit": EditFileTool(),
            "list": ListFilesTool(),
        }

    def run(self) -> int:
        """Start the interactive REPL loop.

        Returns:
            Exit code (0 for success).
        """
        self._running = True
        self._print_welcome()

        try:
            while self._running:
                self._process_input()
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
        except EOFError:
            print("\n\nEnd of input.")
        finally:
            self._print_goodbye()

        return 0

    def _print_welcome(self) -> None:
        """Print welcome message."""
        print(f"\n{self._app.config.app_name} v{self._app.config.version}")
        print("Type 'exit' or 'quit' to leave, 'help' for commands.\n")

    def _print_goodbye(self) -> None:
        """Print goodbye message."""
        print("\nGoodbye!\n")

    def _print_help(self) -> None:
        """Print help message."""
        print("\nAvailable commands:")
        print("  exit, quit    - Exit Friday")
        print("  help          - Show this help message")
        print("  clear         - Clear conversation (future)")
        print("  read <path>   - Read a file")
        print("  write <path>  - Write to a file (multi-line mode)")
        print("  edit <path>   - Edit a file (interactive mode)")
        print("  list [path]   - List files in directory (default: current)")
        print("  /plan <goal>  - Generate and execute a multi-step plan")
        print("\nOr just type your message to chat with Friday.\n")

    def _process_input(self) -> None:
        """Process one input cycle."""
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            raise

        if not user_input:
            return

        # Handle commands
        if user_input.lower() in ("exit", "quit"):
            self._running = False
            return

        if user_input.lower() == "help":
            self._print_help()
            return

        if user_input.lower() == "clear":
            print("(Conversation clearing not yet implemented)")
            return

        # Handle tool commands
        if user_input.lower().startswith("read "):
            path = user_input[5:].strip()
            self._handle_read_file(path)
            return

        if user_input.lower().startswith("write "):
            path = user_input[6:].strip()
            self._handle_write_file(path)
            return

        if user_input.lower().startswith("edit "):
            path = user_input[5:].strip()
            self._handle_edit_file(path)
            return

        if user_input.lower().startswith("list"):
            # "list" or "list <path>"
            path = user_input[4:].strip() if len(user_input) > 4 else "."
            self._handle_list_files(path)
            return

        if user_input.lower().startswith("/plan "):
            goal = user_input[6:].strip()
            self._handle_plan(goal)
            return

        # Send to LLM
        self._handle_message(user_input)

    def _handle_message(self, message: str) -> None:
        """Send message to Agent (with function calling) and print response.

        Args:
            message: User's message.
        """
        try:
            # Use agent instead of direct LLM call
            response = self._agent.run(message)
            print(f"\nFriday: {response}\n")
        except Exception as exc:
            print(f"\n❌ Error: {exc}\n")
            self._app.logger.exception("REPL error during message handling")

    def _handle_read_file(self, path: str) -> None:
        """Handle read file command.

        Args:
            path: File path to read.
        """
        if not path:
            print("\n❌ Error: Please provide a file path\n")
            return

        tool = self._tools["read"]
        result = tool.execute(path=path)

        if result.success:
            print(f"\n📄 File content ({path}):\n")
            print(result.output)
            print()
        else:
            print(f"\n❌ Error: {result.error}\n")

    def _handle_write_file(self, path: str) -> None:
        """Handle write file command.

        Args:
            path: File path to write.
        """
        if not path:
            print("\n❌ Error: Please provide a file path\n")
            return

        print("\nEnter content (press Enter on empty line to finish):\n")

        lines = []
        try:
            while True:
                line = input()
                # Empty line ends input
                if not line:
                    break
                lines.append(line)
        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ Write cancelled\n")
            return

        content = "\n".join(lines)

        tool = self._tools["write"]
        result = tool.execute(path=path, content=content)

        if result.success:
            print(f"\n✅ {result.output}\n")
        else:
            print(f"\n❌ Error: {result.error}\n")

    def _handle_edit_file(self, path: str) -> None:
        """Handle edit file command with interactive mode.

        Args:
            path: File path to edit.
        """
        if not path:
            print("\n❌ Error: Please provide a file path\n")
            return

        # Show available operations
        print("\n📝 Edit operations:")
        print("  1. replace_lines  - Replace specific line(s)")
        print("  2. insert_after   - Insert content after a line")
        print("  3. delete_lines   - Delete specific line(s)")
        print("  4. find_replace   - Find and replace text")
        print("  0. cancel\n")

        try:
            choice = input("Select operation (0-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ Edit cancelled\n")
            return

        if choice == "0":
            print("\n❌ Edit cancelled\n")
            return

        tool = self._tools["edit"]
        kwargs = {"path": path}

        try:
            if choice == "1":
                kwargs["operation"] = "replace_lines"
                line_num = int(input("Line number to replace: ").strip())
                print("New content (press Enter on empty line to finish):")
                content_lines = []
                while True:
                    line = input()
                    if not line:
                        break
                    content_lines.append(line)
                kwargs["line_number"] = line_num  # type: ignore[assignment]
                kwargs["content"] = "\n".join(content_lines)

            elif choice == "2":
                kwargs["operation"] = "insert_after"
                line_num = int(input("Insert after line number: ").strip())
                print("Content to insert (press Enter on empty line to finish):")
                content_lines = []
                while True:
                    line = input()
                    if not line:
                        break
                    content_lines.append(line)
                kwargs["line_number"] = line_num  # type: ignore[assignment]
                kwargs["content"] = "\n".join(content_lines)

            elif choice == "3":
                kwargs["operation"] = "delete_lines"
                lines_input = input(
                    "Line numbers to delete (comma-separated): "
                ).strip()
                line_numbers = [int(x.strip()) for x in lines_input.split(",")]
                kwargs["line_numbers"] = line_numbers  # type: ignore[assignment]

            elif choice == "4":
                kwargs["operation"] = "find_replace"
                find_text = input("Text to find: ").strip()
                replace_text = input("Replace with: ").strip()
                use_regex = input("Use regex? (y/n): ").strip().lower() == "y"
                kwargs["find"] = find_text
                kwargs["replace"] = replace_text
                kwargs["regex"] = use_regex  # type: ignore[assignment]

            else:
                print("\n❌ Invalid choice\n")
                return

            result = tool.execute(**kwargs)

            if result.success:
                print(f"\n✅ {result.output}\n")
            else:
                print(f"\n❌ Error: {result.error}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ Edit cancelled\n")
        except ValueError as exc:
            print(f"\n❌ Invalid input: {exc}\n")

    def _handle_list_files(self, path: str) -> None:
        """Handle list files command.

        Args:
            path: Directory path to list.
        """
        if not path:
            path = "."

        tool = self._tools["list"]
        result = tool.execute(path=path)

        if result.success:
            print(f"\n{result.output}\n")
        else:
            print(f"\n❌ Error: {result.error}\n")

    def _handle_plan(self, goal: str) -> None:
        """Handle the /plan command to generate and execute a multi-step plan.

        Args:
            goal: The user's requested goal.
        """
        if not goal:
            print(
                "\n❌ Error: Please provide a goal "
                "(e.g. /plan write tests for planner)\n"
            )
            return

        print("\n⏳ Generating plan...")
        planner = TaskPlanner(self._app.provider)
        try:
            plan = planner.generate_plan(goal)
            print("\n📋 Plan generated:\n")
            print(plan.format_status())

            confirm = input("\nExecute this plan? (y/n): ").strip().lower()
            if confirm != "y":
                print("\n❌ Plan execution cancelled.\n")
                return

            print("\n🚀 Executing plan...\n")
            executor = PlanExecutor(self._agent)
            success = executor.execute_plan(plan)

            if success:
                print("\n✅ Plan executed successfully!\n")
            else:
                print("\n❌ Plan execution failed or stopped.\n")

            # Print final status
            print(plan.format_status())
            print()

        except Exception as exc:
            print(f"\n❌ Error generating or executing plan: {exc}\n")
            self._app.logger.exception("Error in /plan command")
