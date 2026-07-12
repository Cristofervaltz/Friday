"""Application-wide constants for Friday.

The values defined here are intentionally small, stable defaults used by the
bootstrap layers of the application.
"""

from __future__ import annotations

APP_NAME = "Friday"
APP_VERSION = "0.0.1"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIRNAME = "logs"
DEFAULT_LOG_FILENAME = "friday.log"
DEFAULT_MAX_LOG_SIZE = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
