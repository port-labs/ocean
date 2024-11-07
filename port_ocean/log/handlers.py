import asyncio
import logging
import sys
import threading
import time
from datetime import datetime
from logging.handlers import MemoryHandler
from typing import Any

from loguru import logger

from port_ocean import Ocean
from port_ocean.context.ocean import ocean
from copy import deepcopy
from traceback import format_exception


def _serialize_record(record: logging.LogRecord) -> dict[str, Any]:
    extra = {**deepcopy(record.__dict__["extra"])}
    if isinstance(extra.get("exc_info"), Exception):
        serialized_exception = "".join(format_exception(extra.get("exc_info")))
        extra["exc_info"] = serialized_exception
    return {
        "message": record.msg,
        "level": record.levelname,
        "timestamp": datetime.utcfromtimestamp(record.created).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
        "extra": extra,
    }


class HTTPMemoryHandler(MemoryHandler):
    def __init__(
        self,
        capacity: int = 100,
        flush_level: int = logging.FATAL,
        flush_interval: int = 5,
        flush_size: int = 1024,
    ):
        super().__init__(capacity, flushLevel=flush_level, target=None)
        self.flush_interval = flush_interval
        self.flush_size = flush_size
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
        for thread in self._thread_pool:
            if thread.is_alive():
                thread.join()

    def flush(self) -> None:
        if self.ocean is None or not self.buffer:
            return

        def _wrap_event_loop(_ocean: Ocean, logs_to_send: list[dict[str, Any]]) -> None:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.send_logs(_ocean, logs_to_send))
            loop.close()

        def clear_thread_pool() -> None:
            for thread in self._thread_pool:
                if not thread.is_alive():
                    self._thread_pool.remove(thread)

        self.acquire()
        logs = list(self._serialized_buffer)
        if logs:
            self.buffer.clear()
            self._serialized_buffer.clear()
            self.last_flush_time = time.time()
            clear_thread_pool()
            thread = threading.Thread(target=_wrap_event_loop, args=(self.ocean, logs))
            thread.start()
            self._thread_pool.append(thread)
        self.release()

    async def send_logs(
        self, _ocean: Ocean, logs_to_send: list[dict[str, Any]]
    ) -> None:
        try:
            await _ocean.port_client.ingest_integration_logs(logs_to_send)
        except Exception as e:
            logger.debug(f"Failed to send logs to Port with error: {e}")
