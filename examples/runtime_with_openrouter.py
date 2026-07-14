"""Example of using OpenRouter through Friday's Runtime.

This demonstrates the recommended way to use Friday: through the Runtime Core
with configuration loaded from environment variables.

Setup:
1. Copy .env.example to .env
2. Configure FRIDAY_LLM_PROVIDER=openrouter
3. Add your API key
4. Run this script
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    print("python-dotenv not installed. Using system environment variables.")
    print("Install it with: pip install python-dotenv")

from src.runtime import FridayApplication

# Initialize Friday application
app = FridayApplication()
app.initialize()

# Check if provider is available
if app._provider is None:
    print("Error: No LLM provider configured!")
    print("Please check your .env file and ensure:")
    print("- FRIDAY_LLM_PROVIDER is set")
    print("- FRIDAY_LLM_API_KEY is set (if required)")
    print("- FRIDAY_LLM_MODEL is set")
    app.shutdown()
    sys.exit(1)

# Use the provider through Runtime
prompt = "What is the purpose of Friday's Runtime Core?"
print(f"Prompt: {prompt}")

try:
    response = app.provider.generate(prompt)
    print(f"\nFriday: {response}")
except Exception as e:
    print(f"\nError: {e}")

# Clean shutdown
app.shutdown()
print("\nApplication shut down successfully.")
