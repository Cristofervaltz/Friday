"""Core runtime application class managing Friday's lifecycle."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from src.config import AppConfig
from src.llm import (
    BaseLLMProvider,
    ConfigurationError,
    OpenAIProvider,
    OpenRouterProvider,
)
from src.logger import LoggerFactory
from src.utils.safe_print import safe_print

if TYPE_CHECKING:
    from pathlib import Path


class FridayApplication:
    """Central application runtime managing Friday's lifecycle.

    FridayApplication is the single point of initialization and coordination
    for all Friday subsystems. It owns configuration, logging, LLM provider,
    and will eventually manage memory, plugins, tools, and session state.

    Usage:
        app = FridayApplication()
        app.initialize()
        return_code = app.run()
        app.shutdown()
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Create a new Friday application runtime.

        Args:
            base_dir: Optional base directory for configuration.
                      Defaults to current working directory.
        """
        self._base_dir = base_dir
        self._config: AppConfig | None = None
        self._logger: logging.Logger | None = None
        self._provider: BaseLLMProvider | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the Friday application runtime.

        Performs the following steps:
        1. Load configuration from environment
        2. Create required runtime directories
        3. Configure logging subsystem
        4. Initialize LLM provider
        5. Mark runtime as ready

        Raises:
            RuntimeError: If initialization is called more than once.
            Exception: If any initialization step fails.
        """
        if self._initialized:
            raise RuntimeError("FridayApplication is already initialized.")

        try:
            self._load_configuration()
            self._create_directories()
            self._configure_logging()
            self._initialize_provider()
            self._initialized = True

            if self._logger:
                self._logger.info("Runtime initialized successfully.")
                self._logger.info("Application ready.")

        except Exception as exc:
            if self._logger:
                self._logger.exception("Runtime initialization failed: %s", exc)
            else:
                safe_print(f"Runtime initialization failed: {exc}")
            self.shutdown()
            raise

    def reload_config(self) -> None:
        """Reload configuration and reinitialize components dynamically."""
        if not self._initialized:
            return

        if self._logger:
            self._logger.info("Reloading configuration...")
        else:
            safe_print("Reloading configuration...")

        self._load_configuration()
        self._initialize_provider()

        if self._logger:
            self._logger.info("Configuration and provider reloaded.")

    def run(self) -> int:
        """Run the Friday application.

        Returns:
            Exit code (0 for success).

        Raises:
            RuntimeError: If called before initialization.
        """
        self._ensure_initialized()

        if self._logger:
            self._logger.info("Application started.")

        # Future: CLI loop, agent loop, or service daemon will run here
        self._print_runtime_info()

        if self._logger:
            self._logger.info("Application execution completed.")

        return 0

    def shutdown(self) -> None:
        """Shutdown the Friday application and release resources.

        This method is safe to call multiple times and will release:
        - LLM provider connections (future)
        - Plugin resources (future)
        - Memory backend (future)
        - Active sessions (future)
        """
        if self._logger and self._initialized:
            self._logger.info("Shutting down runtime...")

        # Future: close provider connections, plugins, memory, sessions
        self._provider = None
        self._initialized = False

        if self._logger:
            self._logger.info("Runtime shutdown complete.")

    @property
    def config(self) -> AppConfig:
        """Return the application configuration.

        Raises:
            RuntimeError: If accessed before initialization.
        """
        self._ensure_initialized()
        assert self._config is not None
        return self._config

    @property
    def logger(self) -> logging.Logger:
        """Return the application logger.

        Raises:
            RuntimeError: If accessed before initialization.
        """
        self._ensure_initialized()
        assert self._logger is not None
        return self._logger

    @property
    def provider(self) -> BaseLLMProvider:
        """Return the LLM provider.

        Raises:
            RuntimeError: If accessed before initialization.
        """
        self._ensure_initialized()
        assert self._provider is not None
        return self._provider

    def _load_configuration(self) -> None:
        """Load application configuration from environment."""
        if self._logger:
            self._logger.info("Loading configuration...")
        else:
            safe_print("Loading configuration...")

        # Load .env file before reading configuration
        load_dotenv()

        self._config = AppConfig.from_environment(self._base_dir)

    def _create_directories(self) -> None:
        """Create required runtime directories."""
        if self._logger:
            self._logger.info("Creating runtime directories...")
        else:
            safe_print("Creating runtime directories...")

        assert self._config is not None
        self._config.paths.ensure_directories()

    def _configure_logging(self) -> None:
        """Configure the logging subsystem."""
        safe_print("Initializing logger...")

        assert self._config is not None
        logger_factory = LoggerFactory()
        logger_factory.configure(self._config.logging)
        self._logger = logger_factory.get_logger(__name__)

        self._logger.info("Logger initialized.")

    def _initialize_provider(self) -> None:
        """Initialize the LLM provider based on configuration."""
        assert self._logger is not None
        self._logger.info("Initializing provider...")

        assert self._config is not None
        provider_type = self._config.llm.provider.lower()

        try:
            if provider_type == "openai":
                self._provider = OpenAIProvider.from_config(self._config.llm)
            elif provider_type == "gemini":
                # Use Google AI Studio's OpenAI compatibility endpoint
                gemini_config = self._config.llm
                if not gemini_config.base_url:
                    from dataclasses import replace

                    gemini_config = replace(
                        gemini_config,
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    )
                self._provider = OpenAIProvider.from_config(gemini_config)
            elif provider_type == "openrouter":
                self._provider = OpenRouterProvider.from_config(self._config.llm)
            elif provider_type == "ollama":
                # Use Ollama's native OpenAI compatibility endpoint to support
                # Function Calling
                ollama_config = self._config.llm
                if not ollama_config.base_url:
                    from dataclasses import replace

                    ollama_config = replace(
                        ollama_config, base_url="http://localhost:11434/v1"
                    )
                if not ollama_config.api_key:
                    from dataclasses import replace

                    ollama_config = replace(ollama_config, api_key="ollama")
                self._provider = OpenAIProvider.from_config(ollama_config)
            else:
                raise ConfigurationError(
                    f"Unknown LLM provider: {provider_type}. "
                    f"Supported providers: openai, gemini, openrouter, ollama."
                )
            self._logger.info("Provider initialized: %s", self._provider.model_name())
        except Exception as exc:
            self._logger.warning(
                "Provider initialization skipped or failed: %s. "
                "Application will continue without LLM capabilities.",
                exc,
            )
            self._provider = None

    def _print_runtime_info(self) -> None:
        """Print runtime information to console and log."""
        assert self._config is not None
        assert self._logger is not None

        message = (
            f"{self._config.app_name} v{self._config.version} initialized "
            f"in {self._config.environment} mode."
        )
        safe_print(message)
        self._logger.info(message)

    def _ensure_initialized(self) -> None:
        """Ensure the application has been initialized.

        Raises:
            RuntimeError: If the application has not been initialized.
        """
        if not self._initialized:
            raise RuntimeError(
                "FridayApplication must be initialized before use. "
                "Call initialize() first."
            )
