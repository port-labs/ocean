import asyncio
import logging
import threading
import time
from datetime import datetime
from logging import LogRecord
from logging.handlers import MemoryHandler

from loguru import logger

from port_ocean import Ocean
from port_ocean.context.ocean import ocean


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

    @property
    def ocean(self) -> Ocean | None:
        # We want to wait for the context to be initialized before we can send logs
        if ocean.initialized:
            return ocean.app
        return None

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        """
        Extending shouldFlush to include size and time validation as part of the decision whether to flush
        """
        if bool(self.buffer) and (
            super(HTTPMemoryHandler, self).shouldFlush(record)
            or sum(len(record.msg) for record in self.buffer) >= self.flush_size
            or time.time() - self.last_flush_time >= self.flush_interval
        ):
            return True
        return False

    def flush(self) -> None:
        if self.ocean is None or not self.buffer:
            return

        def _wrap_event_loop(logs_to_send: list[LogRecord]) -> None:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.send_logs(logs_to_send))
            loop.close()

        self.acquire()
        logs = list(self.buffer)
        if logs:
            self.buffer.clear()
            self.last_flush_time = time.time()
            threading.Thread(target=_wrap_event_loop, args=(logs,)).start()
        self.release()

    async def send_logs(self, logs_to_send: list[LogRecord]) -> None:
        raw_logs = [
            {
                "message": record.msg,
                "level": record.levelname,
                "timestamp": datetime.utcfromtimestamp(record.created).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
                "extra": record.__dict__["extra"],
            }
            for record in logs_to_send
        ]
        try:
            await self.ocean.port_client.ingest_integration_logs(raw_logs)
        except Exception as e:
            logger.debug(f"Failed to send logs to Port with error: {e}")
