import sys

from loguru import logger

from port_ocean.config.integration import LogLevelType


def setup_logger(level: LogLevelType) -> None:
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level> | {extra}"
    )

    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format=logger_format,
        enqueue=True,  # process logs in background
        diagnose=False,  # hide variable values in log backtrace
    )
