"""Example of using LM Studio with Friday.

LM Studio is compatible with the Ollama provider when configured correctly.
This example shows how to connect to LM Studio's local server.

Setup:
1. Download LM Studio: https://lmstudio.ai
2. Load a model in LM Studio
3. Start the local server (usually on port 1234)
4. Update model name below to match your loaded model
5. Run this script

No API key required for LM Studio!
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.llm import OllamaProvider

# LM Studio typically runs on http://localhost:1234
# and exposes an OpenAI-compatible API
provider = OllamaProvider(
    model="local-model",  # Replace with your loaded model name in LM Studio
    base_url="http://localhost:1234",
)

prompt = "What is Friday designed for?"
print(f"Prompt: {prompt}")
print(f"Connecting to LM Studio at {provider._base_url}...")

try:
    response = provider.generate(prompt)
    print(f"\nFriday: {response}")
except Exception as e:
    print(f"\nError: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure LM Studio is running")
    print("2. Check that a model is loaded")
    print("3. Verify the local server is started (green indicator)")
    print("4. Confirm the port matches (default: 1234)")
    print("5. Update the 'model' parameter to match your loaded model name")
