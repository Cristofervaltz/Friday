# Examples

This directory contains practical examples demonstrating how to use Friday with different LLM providers.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and add your configuration:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys and preferred settings.

**Important:** Never commit `.env` file! It contains sensitive information.

## Available Examples

### OpenRouter Examples

**`basic_openrouter.py`** — Direct OpenRouter provider usage

```bash
python examples/basic_openrouter.py
```

**`runtime_with_openrouter.py`** — OpenRouter through Runtime (recommended)

```bash
python examples/runtime_with_openrouter.py
```

**Requirements:**
- OpenRouter API key (get one at https://openrouter.ai)
- Sufficient balance on OpenRouter account

### Local Model Examples

**`basic_ollama.py`** — Ollama for local models

```bash
python examples/basic_ollama.py
```

**Requirements:**
- Ollama installed (https://ollama.ai)
- At least one model pulled: `ollama pull llama2`
- No API key needed!

**`lm_studio.py`** — LM Studio integration

```bash
python examples/lm_studio.py
```

**Requirements:**
- LM Studio installed (https://lmstudio.ai)
- Model loaded in LM Studio
- Local server started
- No API key needed!

### Configuration Examples

**`config_override.py`** — Programmatic configuration override

```bash
python examples/config_override.py
```

Shows how to override configuration at runtime (useful for testing).

## Quick Start

### Using OpenRouter (Cloud)

1. Get API key from https://openrouter.ai
2. Edit `.env`:
   ```
   FRIDAY_LLM_PROVIDER=openrouter
   FRIDAY_LLM_API_KEY=sk-or-v1-your-key-here
   FRIDAY_LLM_MODEL=openai/gpt-4-turbo
   ```
3. Run: `python examples/runtime_with_openrouter.py`

### Using Ollama (Local)

1. Install Ollama: `curl https://ollama.ai/install.sh | sh`
2. Pull model: `ollama pull llama2`
3. Edit `.env`:
   ```
   FRIDAY_LLM_PROVIDER=ollama
   FRIDAY_LLM_MODEL=llama2
   ```
4. Run: `python examples/basic_ollama.py`

### Using LM Studio (Local)

1. Download LM Studio from https://lmstudio.ai
2. Load a model (e.g., Llama 2)
3. Start local server
4. Run: `python examples/lm_studio.py`

## Security Notes

- **Never commit** `.env` file
- **Never hardcode** API keys in examples
- Keep `.env.example` as a template only
- Use environment variables for sensitive data

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"

Make sure you're running from the project root or the examples already include the correct path setup.

### "Error 402: Payment Required" (OpenRouter)

Your OpenRouter account needs balance. Add credits at https://openrouter.ai

### "Connection refused" (Ollama/LM Studio)

- Verify Ollama is running: `ollama list`
- Check LM Studio local server is started
- Confirm correct port (11434 for Ollama, 1234 for LM Studio)

### "Provider initialization failed"

Check your `.env` file:
- Correct provider name
- Valid API key (if required)
- Model is available

## More Information

- [Main README](../README.md)
- [Configuration Reference](../docs/)
- [LLM Provider Documentation](../src/llm/)
