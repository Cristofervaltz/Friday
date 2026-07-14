"""Example of configuration override patterns.

This demonstrates how to programmatically override Friday's configuration
before initializing the Runtime.

Note: For production use, prefer .env file over hardcoded values.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Override configuration through environment variables
# In production, these should come from .env file
os.environ["FRIDAY_LLM_PROVIDER"] = "openrouter"
os.environ["FRIDAY_LLM_MODEL"] = "anthropic/claude-3-sonnet"
os.environ["FRIDAY_LLM_API_KEY"] = os.getenv("FRIDAY_LLM_API_KEY", "your-api-key-here")
os.environ["FRIDAY_LOG_LEVEL"] = "DEBUG"
os.environ["FRIDAY_LLM_TIMEOUT"] = "60"

from src.runtime import FridayApplication

app = FridayApplication()

try:
    app.initialize()
except Exception as e:
    print(f"Initialization failed: {e}")
    print("\nMake sure your .env file is configured correctly.")
    sys.exit(1)

# Verify configuration
print(f"Provider: {app.config.llm.provider}")
print(f"Model: {app.provider.model_name()}")
print(f"Log Level: {app.config.logging.level}")
print(f"Timeout: {app.config.llm.timeout}s")

# Test the provider (only if API key is valid)
if app._provider and os.getenv("FRIDAY_LLM_API_KEY") != "your-api-key-here":
    try:
        response = app.provider.generate("Say hello in one word.")
        print(f"\nResponse: {response}")
    except Exception as e:
        print(f"\nError: {e}")
else:
    print("\nSkipping provider test (no valid API key)")

app.shutdown()
