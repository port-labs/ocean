import logging
from pathlib import PosixPath
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime
from logging.handlers import MemoryHandler
from traceback import format_exception
from typing import Any

from loguru import logger

from port_ocean import Ocean
from port_ocean.context.ocean import ocean
from port_ocean.utils.misc import run_async_in_new_event_loop


def _serialize_posix_paths(
    extra: dict[str, Any], max_depth: int = 100
) -> dict[str, Any]:
    if max_depth <= 0:
        logger.warning("Max depth reached, skipping path removal")
        return extra
    for key, value in extra.items():
        if isinstance(value, list):
            value = [
                (
                    _serialize_posix_paths(item, max_depth - 1)
                    if isinstance(item, dict)
                    else item
                )
                for item in value
            ]
        elif isinstance(value, dict):
            value = _serialize_posix_paths(value, max_depth - 1)
        elif isinstance(value, PosixPath):
            extra[key] = str(value)
    return extra


def _serialize_record(record: logging.LogRecord) -> dict[str, Any]:
    extra = {**deepcopy(record.__dict__["extra"])}
    if isinstance(extra.get("exc_info"), Exception):
        serialized_exception = "".join(format_exception(extra.get("exc_info")))
        extra["exc_info"] = serialized_exception
    extra = _serialize_posix_paths(extra)
    return {
        "message": record.msg.rstrip(
            "\n"
        ),  # strip trailing newline that exception messages and multiline strings can leave
        "level": record.levelname,
        "timestamp": datetime.utcfromtimestamp(record.created).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
        "extra": extra,
    }


# Cap how long shutdown waits on log-shipping threads. Without a timeout,
# a stuck ingest (or fail→reflush loop) blocks process exit forever.
LOG_SHIP_JOIN_TIMEOUT_SECONDS = 30.0


class HTTPMemoryHandler(MemoryHandler):
    def __init__(
        self,
        capacity: int = 100,
        flush_level: int = logging.FATAL,
        flush_interval: int = 5,
        flush_size: int = 1024,
        join_timeout_seconds: float = LOG_SHIP_JOIN_TIMEOUT_SECONDS,
    ):
        super().__init__(capacity, flushLevel=flush_level, target=None)
        self.flush_interval = flush_interval
        self.flush_size = flush_size
        self.join_timeout_seconds = join_timeout_seconds
        self.last_flush_time = time.time()
        self._serialized_buffer: list[dict[str, Any]] = []
        self._thread_pool: list[threading.Thread] = []

    @property
    def ocean(self) -> Ocean | None:
        # We want to wait for the context to be initialized before we can send logs
        if ocean.initialized:
            return ocean.app
        return None

    def emit(self, record: logging.LogRecord) -> None:
        self._serialized_buffer.append(_serialize_record(record))
        super().emit(record)

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        """
        Extending shouldFlush to include size and time validation as part of the decision whether to flush
        """
        if bool(self.buffer) and (
            super(HTTPMemoryHandler, self).shouldFlush(record)
            or sys.getsizeof(self.buffer) >= self.flush_size
            or time.time() - self.last_flush_time >= self.flush_interval
        ):
            return True
        return False

    def wait_for_lingering_threads(self) -> None:
        # Snapshot: joining a live list while failed sends append new threads
        # can loop forever during ingest outages.
        for thread in list(self._thread_pool):
            if thread.is_alive():
                thread.join(timeout=self.join_timeout_seconds)

    def flush(self) -> None:
        if self.ocean is None or not self.buffer:
            return

        def _wrap_event_loop(_ocean: Ocean, logs_to_send: list[dict[str, Any]]) -> None:
            run_async_in_new_event_loop(self.send_logs(_ocean, logs_to_send))

        def clear_thread_pool() -> None:
            for thread in self._thread_pool:
                if not thread.is_alive():
                    self._thread_pool.remove(thread)

        self.acquire()
        try:
            logs = list(self._serialized_buffer)
            if logs:
                self.buffer.clear()
                self._serialized_buffer.clear()
                self.last_flush_time = time.time()
                clear_thread_pool()
                thread = threading.Thread(
                    target=_wrap_event_loop,
                    args=(self.ocean, logs),
                    daemon=True,
                    name="ocean-log-ship",
                )
                thread.start()
                self._thread_pool.append(thread)
        finally:
            self.release()

    async def send_logs(
        self, _ocean: Ocean, logs_to_send: list[dict[str, Any]]
    ) -> None:
        try:
            await _ocean.port_client.ingest_integration_logs(logs_to_send)
        except Exception as e:
            # local_only: do not re-ingest this error — that starts another ship
            # thread and can loop forever while Port ingest is down.
            logger.bind(local_only=True).error(
                f"Failed to send logs to Port with error: {e}"
            )
