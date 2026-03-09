import sys
from collections import namedtuple

from port_ocean.log.handlers import _serialize_record
from port_ocean.log.logger_setup import _extract_traceback
from loguru import logger
from logging import LogRecord
from queue import Queue
from logging.handlers import QueueHandler
from typing import Callable, Any

# Matches the shape of loguru's internal RecordException namedtuple
_RecordException = namedtuple("_RecordException", ["type", "value", "traceback"])


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
    message = serialized_record.get("message", None)
    assert message is not None and log_message in message


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


def test_extract_traceback_with_real_exception() -> None:
    """When a real exception is caught, traceback should be extracted into extra."""
    try:
        raise ValueError("real error")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    record: dict = {
        "extra": {},
        "exception": _RecordException(exc_type, exc_value, exc_tb),
    }
    _extract_traceback(record)

    assert "traceback" in record["extra"]
    assert "ValueError" in record["extra"]["traceback"]
    assert "real error" in record["extra"]["traceback"]


def test_extract_traceback_without_traceback() -> None:
    """Manually created exception (no traceback) should not set extra['traceback']."""
    exc_value = ValueError("manual error")
    record: dict = {
        "extra": {},
        "exception": _RecordException(ValueError, exc_value, None),
    }
    _extract_traceback(record)

    assert "traceback" not in record["extra"]


def test_extract_traceback_no_exception() -> None:
    """When there is no exception, extra should remain unchanged."""
    record: dict = {"extra": {}, "exception": None}
    _extract_traceback(record)

    assert "traceback" not in record["extra"]


def assert_extra(extra: dict[str, Any]) -> str:
    exc_info = extra.get("exc_info", None)
    assert isinstance(exc_info, str)
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
