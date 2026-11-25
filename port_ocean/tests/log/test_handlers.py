import logging
import sys
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from port_ocean.log.handlers import HTTPMemoryHandler, _serialize_record
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

    record: dict[str, Any] = {
        "extra": {},
        "exception": _RecordException(exc_type, exc_value, exc_tb),
    }
    _extract_traceback(record)  # type: ignore[arg-type]

    assert "traceback" in record["extra"]
    assert "ValueError" in record["extra"]["traceback"]
    assert "real error" in record["extra"]["traceback"]


def test_extract_traceback_without_traceback() -> None:
    """Manually created exception (no traceback) should not set extra['traceback']."""
    exc_value = ValueError("manual error")
    record: dict[str, Any] = {
        "extra": {},
        "exception": _RecordException(ValueError, exc_value, None),
    }
    _extract_traceback(record)  # type: ignore[arg-type]

    assert "traceback" not in record["extra"]


def test_extract_traceback_no_exception() -> None:
    """When there is no exception, extra should remain unchanged."""
    record: dict[str, Any] = {"extra": {}, "exception": None}
    _extract_traceback(record)  # type: ignore[arg-type]

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


def test_flush_releases_lock_when_it_fails() -> None:
    handler = HTTPMemoryHandler(capacity=100, flush_level=logging.FATAL)
    handler.buffer.append(MagicMock())
    handler._serialized_buffer.append({"message": log_message})
    handler.lock = MagicMock()

    with (
        patch.object(
            HTTPMemoryHandler,
            "ocean",
            new_callable=PropertyMock,
            return_value=MagicMock(),
        ),
        patch(
            "port_ocean.log.handlers.threading.Thread",
            side_effect=RuntimeError("thread failure"),
        ),
        pytest.raises(RuntimeError),
    ):
        handler.flush()

    handler.lock.release.assert_called_once()


def test_flush_starts_daemon_log_ship_thread() -> None:
    handler = HTTPMemoryHandler(capacity=100, flush_level=logging.FATAL)
    handler.buffer.append(MagicMock())
    handler._serialized_buffer.append({"message": log_message})
    mock_thread = MagicMock()

    with (
        patch.object(
            HTTPMemoryHandler,
            "ocean",
            new_callable=PropertyMock,
            return_value=MagicMock(),
        ),
        patch(
            "port_ocean.log.handlers.threading.Thread",
            return_value=mock_thread,
        ) as thread_cls,
    ):
        handler.flush()

    kwargs = thread_cls.call_args.kwargs
    assert kwargs["daemon"] is True
    assert kwargs["name"] == "ocean-log-ship"
    mock_thread.start.assert_called_once()


def test_wait_for_lingering_threads_joins_with_timeout() -> None:
    handler = HTTPMemoryHandler(
        capacity=100, flush_level=logging.FATAL, join_timeout_seconds=1.5
    )
    alive = MagicMock()
    alive.is_alive.return_value = True
    dead = MagicMock()
    dead.is_alive.return_value = False
    handler._thread_pool = [alive, dead]

    handler.wait_for_lingering_threads()

    alive.join.assert_called_once_with(timeout=1.5)
    dead.join.assert_not_called()


@pytest.mark.asyncio
async def test_send_logs_failure_is_local_only() -> None:
    handler = HTTPMemoryHandler(capacity=100, flush_level=logging.FATAL)
    ocean_app = MagicMock()
    ocean_app.port_client.ingest_integration_logs = AsyncMock(
        side_effect=RuntimeError("ingest down")
    )

    bound = MagicMock()
    with patch("port_ocean.log.handlers.logger") as mock_logger:
        mock_logger.bind.return_value = bound
        await handler.send_logs(ocean_app, [{"message": "x"}])

    mock_logger.bind.assert_called_once_with(local_only=True)
    bound.error.assert_called_once()
