"""Global logger for setup scripts."""

from __future__ import annotations

import logging
import sys

_LOGGER_NAME = "scripts.aws-v3"

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(message)s"))

logger = logging.getLogger(_LOGGER_NAME)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False
