from port_ocean.log.handlers import _serialize_record
from loguru import logger
from logging import LogRecord
from queue import Queue
from logging.handlers import QueueHandler
from typing import Callable, Any


log_message = "This is a test log message."
exception_grouop_message = "Test Exception group"
exception_message = "Test Exception"
expected_keys = ["message", "level", "timestamp", "extra"]


def test_serialize_record_log_shape() -> None:
    record = log_record(
        lambda: logger.exception(
            log_message,
            exc_info=None,
        )
    )
    serialized_record = _serialize_record(record)
    assert all(key in serialized_record for key in expected_keys)
    assert log_message in serialized_record.get("message", None)


def test_serialize_record_exc_info_single_exception() -> None:
    record = log_record(
        lambda: logger.exception(
            log_message,
            exc_info=ExceptionGroup(
                exception_grouop_message, [Exception(exception_message)]
            ),
        )
    )
    serialized_record = _serialize_record(record)
    exc_info = assert_extra(serialized_record.get("extra", {}))
    assert exception_grouop_message in exc_info
    assert exception_message in exc_info


def test_serialize_record_exc_info_group_exception() -> None:
    record = log_record(
        lambda: logger.exception(log_message, exc_info=Exception(exception_message))
    )
    serialized_record = _serialize_record(record)
    exc_info = assert_extra(serialized_record.get("extra", {}))
    assert exception_message in exc_info


def assert_extra(extra: dict[str, Any]) -> str:
    exc_info = extra.get("exc_info", None)
    assert type(exc_info) is str
    return exc_info


def log_record(cb: Callable[[], None]) -> LogRecord:
    queue = Queue[LogRecord]()
    queue_handler = QueueHandler(queue)
    logger_id = logger.add(
        queue_handler,
        level="DEBUG",
        format="{message}",
        diagnose=False,
        enqueue=True,
    )
    cb()
    logger.complete()
    logger.remove(logger_id)
    record = queue.get()
    return record
