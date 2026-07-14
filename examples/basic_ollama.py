"""Basic example of using Ollama provider for local LLM inference.

This example demonstrates how to use Ollama to run local language models.
Ollama must be running on localhost:11434 with at least one model installed.

Setup:
1. Install Ollama: https://ollama.ai
2. Pull a model: ollama pull llama2
3. Start Ollama (it runs as a service)
4. Run this script

No API key required for Ollama!
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.llm import OllamaProvider

# Initialize Ollama provider
# No API key needed - it connects to local Ollama instance
provider = OllamaProvider(
    model="llama2",
    base_url="http://localhost:11434",
)

# Generate a response
prompt = "Hello, Friday! What can you help me with?"
print(f"Prompt: {prompt}")

try:
    response = provider.generate(prompt)
    print(f"\nFriday: {response}")
except Exception as e:
    print(f"\nError: {e}")
    print("\nMake sure Ollama is running and you have pulled the model:")
    print("  ollama pull llama2")
    print("\nCheck Ollama status:")
    print("  ollama list")
