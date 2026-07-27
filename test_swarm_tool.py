import sys
sys.path.insert(0, r"c:\Users\Klim\OneDrive\Desktop\Friday")
from src.tools.swarm_tool import DelegateTaskTool

class MockConfig:
    class paths:
        data_dir = None

class MockApp:
    config = MockConfig()
    provider = None
    repl = None

tool = DelegateTaskTool(MockApp(), None)
try:
    result = tool.execute(role="test", task="test")
    print("Success:", result.success)
    if result.error:
        print("Error:", result.error)
except Exception as e:
    print("Exception:", e)
