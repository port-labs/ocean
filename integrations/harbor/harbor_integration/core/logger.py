"""
loguru config file
"""

import os
import sys
from pathlib import Path
from loguru import logger

# --------------------------------------------------------------------------- #
# CONFIGURATION
# --------------------------------------------------------------------------- #

# Log level (default: DEBUG for local, INFO for prod)
LOG_LEVEL = os.getenv("HARBOR_LOG_LEVEL", "DEBUG").upper()

# Log directory & file
LOG_DIR = Path(os.getenv("HARBOR_LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / os.getenv("HARBOR_LOG_FILE", "harbor_integration.log")

# Console
CONSOLE_ENABLED = os.getenv("HARBOR_LOG_CONSOLE", "true").lower() == "true"

# File logging
FILE_ENABLED = os.getenv("HARBOR_LOG_FILE_ENABLED", "true").lower() == "true"
FILE_ROTATION = os.getenv("HARBOR_LOG_ROTATION", "10 MB")
FILE_RETENTION = os.getenv("HARBOR_LOG_RETENTION", "7 days")

# JSON logs (for Datadog, ELK, etc.)
JSON_ENABLED = os.getenv("HARBOR_LOG_JSON", "false").lower() == "true"
JSON_FILE = LOG_DIR / "harbor_{time:YYYY-MM-DD}.jsonl"

# --------------------------------------------------------------------------- #
# SETUP
# --------------------------------------------------------------------------- #

logger.remove()  # Clear default handler

# 1. Console → stderr (Ocean-safe)
if CONSOLE_ENABLED:
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True,
        catch=True,
    )

# 2. File → rotated plain text
if FILE_ENABLED:
    logger.add(
        LOG_FILE,
        level=LOG_LEVEL,
        rotation=FILE_ROTATION,
        retention=FILE_RETENTION,
        compression="zip",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | {name}:{function}:{line} | {message}"
        ),
        backtrace=True,
        diagnose=True,
        enqueue=True,
        catch=True,
    )

# 3. JSON file → structured logs
if JSON_ENABLED:
    logger.add(
        JSON_FILE,
        level="INFO",
        rotation="00:00",  # Daily
        retention="30 days",
        serialize=True,
        enqueue=True,
        catch=True,
    )

# --------------------------------------------------------------------------- #
# EXPORT
# --------------------------------------------------------------------------- #

__all__ = ["logger"]
