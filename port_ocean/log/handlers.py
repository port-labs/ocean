import logging
import json
import asyncio
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

_MAX_LOG_BATCH_BYTES = 1_000_000  # 1 MB log size limit


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
            run_async_in_new_event_loop(self.send_logs(_ocean, logs_to_send))

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

    def _split_logs_into_size_bounded_chunks(
        self, logs: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        chunks: list[list[dict[str, Any]]] = []
        current_chunk: list[dict[str, Any]] = []
        current_chunk_size = 0

        for log in logs:
            log_size = len(json.dumps(log).encode())
            if current_chunk and current_chunk_size + log_size > _MAX_LOG_BATCH_BYTES:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_size = 0

            current_chunk.append(log)
            current_chunk_size += log_size

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _send_logs_chunked(
        self, _ocean: Ocean, logs: list[dict[str, Any]]
    ) -> None:
        if not logs:
            return

        result = await asyncio.gather(
            *[
                _ocean.port_client.ingest_integration_logs(logs=logs_chunk)
                for logs_chunk in self._split_logs_into_size_bounded_chunks(logs)
            ],
            return_exceptions=True,
        )
        for chunk_result in result:
            if isinstance(chunk_result, Exception):
                logger.error(f"Failed to send logs chunk: {chunk_result}")

    async def send_logs(
        self, _ocean: Ocean, logs_to_send: list[dict[str, Any]]
    ) -> None:
        await self._send_logs_chunked(_ocean, logs_to_send)
