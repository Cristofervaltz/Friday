import sys
sys.path.insert(0, r"c:\Users\Klim\OneDrive\Desktop\Friday")

from src.runtime.application import FridayApplication
from src.tools.swarm_tool import DelegateTaskTool
from src.core.tool_registry import ToolRegistry

app = FridayApplication()
app.initialize()

registry = ToolRegistry()
tool = DelegateTaskTool(app=app, registry=registry)

result = tool.execute(role="test role", task="test task")
print(f"Success: {result.success}")
if not result.success:
    print(f"Error: {result.error}")
else:
    print(f"Output: {result.output}")
