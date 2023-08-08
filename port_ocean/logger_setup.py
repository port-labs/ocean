import sys

import loguru
from loguru import logger

from port_ocean.config.settings import LogLevelType


def setup_logger(level: LogLevelType) -> None:
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    if level == "DEBUG":
        logger_format += " | {extra}"

    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format=logger_format,
        enqueue=True,  # process logs in background
        diagnose=False,  # hide variable values in log backtrace
    )
    logger.configure(patcher=exception_deserializer)


def exception_deserializer(record: "loguru.Record") -> None:
    """
    Workaround for when trying to log exception objects with loguru.
    loguru doesn't able to deserialize `Exception` subclasses.
    https://github.com/Delgan/loguru/issues/504#issuecomment-917365972
    """
    exception: loguru.RecordException | None = record["exception"]
    if exception is not None:
        fixed = Exception(str(exception.value))
        record["exception"] = exception._replace(value=fixed)
