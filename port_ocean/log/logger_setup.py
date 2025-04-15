import sys
import os
from logging import LogRecord
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
import uuid

import loguru
from loguru import logger

from port_ocean.config.settings import LogLevelType
from port_ocean.log.handlers import HTTPMemoryHandler
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.utils.signal import signal_handler


def setup_logger(level: LogLevelType, enable_http_handler: bool) -> None:
    logger.remove()
    logger.configure(
        extra={"hostname": resolve_hostname(), "instance": str(uuid.uuid4())}
    )
    _stdout_loguru_handler(level)
    if enable_http_handler:
        _http_loguru_handler(level)


def _stdout_loguru_handler(level: LogLevelType) -> None:
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    if level == "DEBUG":
        logger_format += " | {extra}"

    logger.add(
        sys.stdout,
        level=level.upper(),
        format=logger_format,
        enqueue=True,  # process logs in background
        diagnose=False,  # hide variable values in log backtrace
        filter=sensitive_log_filter.create_filter(),
    )
    logger.configure(patcher=exception_deserializer)


def _http_loguru_handler(level: LogLevelType) -> None:
    queue: Queue[LogRecord] = Queue()

    handler = QueueHandler(queue)

    logger.add(
        handler,
        level=level.upper(),
        format="{message}",
        diagnose=False,  # hide variable values in log backtrace
        enqueue=True,  # process logs in background
        filter=sensitive_log_filter.create_filter(full_hide=True),
    )
    logger.configure(patcher=exception_deserializer)

    http_memory_handler = HTTPMemoryHandler()
    signal_handler.register(http_memory_handler.wait_for_lingering_threads)
    signal_handler.register(http_memory_handler.flush)

    queue_listener = QueueListener(queue, http_memory_handler)
    queue_listener.start()


def exception_deserializer(record: "loguru.Record") -> None:
    """
    Workaround for when trying to log exception objects with loguru.
    Loguru doesn't able to deserialize `Exception` subclasses.
    https://github.com/Delgan/loguru/issues/504#issuecomment-917365972
    """
    exception: loguru.RecordException | None = record["exception"]
    if exception is not None:
        fixed = Exception(str(exception.value))
        record["exception"] = exception._replace(value=fixed)


def resolve_hostname() -> str:
    try:
        return os.uname().nodename
    except Exception:
        return "unknown"
