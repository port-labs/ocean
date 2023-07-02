import sys

from loguru import logger

from port_ocean.config.integration import LoggerConfiguration


def setup_logger() -> None:
    settings = LoggerConfiguration()
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level> | {extra}"
    )

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.level.upper(),
        format=logger_format,
        serialize=settings.serialize,
        enqueue=True,  # process logs in background
        diagnose=False,  # hide variable values in log backtrace
    )
