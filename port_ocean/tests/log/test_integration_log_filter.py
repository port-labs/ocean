from logging import LogRecord
from logging.handlers import QueueHandler
from queue import Empty, Queue

from loguru import logger

from port_ocean.log.logger_setup import _http_log_filter
from port_ocean.log.sensetive import sensitive_log_filter


def test_sensitive_filter_still_applies_to_local_only_logs() -> None:
    # Verifies that local_only logs are still scrubbed by the sensitive filter
    # before reaching stdout — the local_only flag must not bypass data redaction.
    # AKIA + 16 uppercase chars matches the Amazon AWS Access Key ID pattern.
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    stdout_queue: Queue[LogRecord] = Queue()
    logger_id = logger.add(
        QueueHandler(stdout_queue),
        level="WARNING",
        format="{message}",
        diagnose=False,
        enqueue=True,
        filter=sensitive_log_filter.create_filter(),
    )

    try:
        logger.bind(local_only=True).warning(f"token: {aws_key}")
        logger.complete()
    finally:
        logger.remove(logger_id)

    records: list[LogRecord] = []
    while True:
        try:
            records.append(stdout_queue.get_nowait())
        except Empty:
            break

    assert len(records) == 1
    assert aws_key not in records[0].msg
    assert "[REDACTED]" in records[0].msg


def test_http_log_filter_excludes_local_only_logs() -> None:
    # Unit test for the filter function itself: a record marked local_only must
    # be rejected (False), while a regular record must be accepted (True).
    local_record = {"extra": {"local_only": True}, "message": "local warning"}
    regular_record = {"extra": {}, "message": "regular warning"}

    assert _http_log_filter(local_record) is False  # type: ignore[arg-type]
    assert _http_log_filter(regular_record) is True  # type: ignore[arg-type]


def test_local_only_warning_never_reaches_http_sink() -> None:
    # Verifies that a local_only log in isolation produces zero entries in the
    # HTTP sink queue — the message must not ship to the integration event log.
    queue: Queue[LogRecord] = Queue()
    queue_handler = QueueHandler(queue)
    logger_id = logger.add(
        queue_handler,
        level="WARNING",
        format="{message}",
        diagnose=False,
        enqueue=True,
        filter=_http_log_filter,
    )

    try:
        logger.bind(local_only=True).warning("local only — must not ship")
        logger.complete()
    finally:
        logger.remove(logger_id)

    assert queue.empty()


def test_local_only_warning_is_blocked_from_http_sink() -> None:
    # Verifies interleaving: regular logs before and after a local_only log both
    # reach the HTTP sink, while the local_only log in the middle does not. This
    # ensures local_only binding does not leak and affect surrounding log calls.
    queue: Queue[LogRecord] = Queue()
    queue_handler = QueueHandler(queue)
    logger_id = logger.add(
        queue_handler,
        level="WARNING",
        format="{message}",
        diagnose=False,
        enqueue=True,
        filter=_http_log_filter,
    )

    try:
        logger.warning("first visible warning")
        logger.bind(local_only=True).warning("hidden local warning")
        logger.warning("second visible warning")
        logger.complete()
    finally:
        logger.remove(logger_id)

    records: list[LogRecord] = []
    while True:
        try:
            records.append(queue.get_nowait())
        except Empty:
            break

    assert len(records) == 2
    assert records[0].msg == "first visible warning"
    assert records[1].msg == "second visible warning"
