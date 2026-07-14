# Changelog

All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog*, and this project follows semantic versioning principles as it matures.

## [0.0.1] - 2026-07-13

### Added
- **Runtime Core** — centralized application lifecycle manager (`FridayApplication`)
- **LLM Provider abstraction** — unified interface for language model providers
- **OpenAI-compatible provider** — first LLM backend with validation, timeouts, and dedicated exceptions
- **OpenRouter provider** — access to multiple LLM providers through OpenRouter API
- **Ollama provider** — support for local LLM hosting (compatible with LM Studio)
- **Provider factory** — automatic provider selection based on configuration
- **Working examples** — practical examples in `examples/` directory for all providers
- Initial open-source repository structure for Friday
- Python 3.12+ project configuration through `pyproject.toml`
- Centralized application configuration with dataclasses
- Reusable logging subsystem with console and rotating file handlers
- Reserved module namespaces for future architecture expansion
- Comprehensive test suite (40 tests) covering configuration, logging, runtime, and all LLM providers
- Quality tooling with Black, Ruff, MyPy, and Pytest
- GitHub Actions CI workflow for validation on pushes and pull requests
- Contributor, roadmap, and repository documentation
- Executable quality check script (`scripts/quality.sh`)

### Changed
- `main.py` simplified to minimal entry point (6 lines)
- Application state now managed through Runtime Core
- All subsystems initialized through centralized Runtime

### Technical
- 40 passing tests with full coverage
- Complete type coverage with MyPy
- Ruff and Black compliant
- Three LLM providers: OpenAI, OpenRouter, Ollama

### Notes
- This release intentionally excludes agent behavior, automation execution, planning, memory systems, plugin architecture, and speech capabilities
- Version `0.0.1` is a foundation release focused on architecture, testing discipline, and extensible LLM integration
- CLI and interactive modes are planned for future releases (v0.1+)
