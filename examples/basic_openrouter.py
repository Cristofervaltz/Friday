"""Basic example of using OpenRouter provider directly.

This example demonstrates how to use OpenRouter to access various LLM models
through a unified API.

Setup:
1. Copy .env.example to .env
2. Add your OpenRouter API key to .env
3. Run this script
"""

import os
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

from src.llm import OpenRouterProvider

# Get configuration from environment
api_key = os.getenv("FRIDAY_LLM_API_KEY")
model = os.getenv("FRIDAY_LLM_MODEL", "openai/gpt-4-turbo")

if not api_key or api_key == "your-api-key-here":
    print("Error: FRIDAY_LLM_API_KEY not set!")
    print("Please:")
    print("1. Copy .env.example to .env")
    print("2. Add your OpenRouter API key")
    print("3. Run this script again")
    sys.exit(1)

# Initialize OpenRouter provider
provider = OpenRouterProvider(
    api_key=api_key,
    model=model,
)

# Generate a response
prompt = "Explain what Friday is in one sentence."
print(f"Prompt: {prompt}")

try:
    response = provider.generate(prompt)
    print(f"\nFriday: {response}")
except Exception as e:
    print(f"\nError: {e}")
    print("\nMake sure your API key is valid and has sufficient balance.")
