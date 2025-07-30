import logging
import sys
from typing import Optional

class ColoredFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.DEBUG: "\033[94m",   # Blue
        logging.INFO: "\033[92m",    # Green
        logging.WARNING: "\033[93m", # Yellow
        logging.ERROR: "\033[91m",   # Red
        logging.CRITICAL: "\033[95m" # Magenta
    }

    RESET_CODE = "\033[0m"

    def format(self, record):
        color = self.COLOR_CODES.get(record.levelno, "")
        reset = self.RESET_CODE
        message = super().format(record)
        return f"{color}{message}{reset}"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or "spacelift_ocean")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = ColoredFormatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)  # Default to DEBUG, tune as needed
        logger.propagate = False
    return logger


logger = get_logger()
