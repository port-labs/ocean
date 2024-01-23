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
from port_ocean.exceptions.context import PortOceanContextNotFoundError

EMPTY_LOG_RECORD = LogRecord("", 0, "", 0, "", (), None)


class HTTPMemoryHandler(MemoryHandler):
    def __init__(
        self,
        capacity: int,
        flush_level: int = logging.FATAL,
        flush_interval: int = 15,
        flush_size: int = 1024,
    ):
        super().__init__(capacity, flushLevel=flush_level, target=None)
        self.flush_interval = flush_interval
        self.flush_size = flush_size
        self.last_flush_time = time.time()
        self._stop = False
        # signal.signal(signal.SIGINT, lambda _, __: self.stop())
        # signal.signal(
        #     signal.SIGTERM,
        #     lambda _, __: logger.debug(
        #         "The application is shutting down flushing all logs into Port"
        #     ),
        # )
        # atexit.register(lambda: self.stop())
        # atexit.register(
        #     lambda: logger.debug(
        #         "The application is shutting down flushing all logs into Port"
        #     )
        # )
        # threading.Timer(self.flush_interval, self.auto_flush).start()

    def stop(self) -> None:
        print("!!!!!!!!!!!!!!!!!!!!!!!!")
        self._stop = True

    @property
    def ocean(self) -> Ocean | None:
        try:
            return ocean.app
        except PortOceanContextNotFoundError:
            return None

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        return bool(self.buffer) and (
            super(HTTPMemoryHandler, self).shouldFlush(record)
            or sum(len(record.msg) for record in self.buffer) >= self.flush_size
            or time.time() - self.last_flush_time >= self.flush_interval
        )

    def flush(self) -> None:
        if self.ocean is None or not self.buffer:
            return

        self.acquire()
        try:
            if self.buffer:
                asyncio.new_event_loop().run_until_complete(self.send_logs(self.buffer))
                self.buffer.clear()
                self.last_flush_time = time.time()
        finally:
            self.release()

    def auto_flush(self) -> None:
        print("auto_flush")
        if self.shouldFlush(EMPTY_LOG_RECORD):
            self.flush()
        if not self._stop:
            threading.Timer(self.flush_interval, self.auto_flush).start()

    async def send_logs(self, logs: list[LogRecord]) -> None:
        raw_logs = [
            {
                "message": record.msg,
                "level": record.levelname,
                "createdAt": datetime.utcfromtimestamp(record.created).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
                "extra": record.__dict__["extra"],
            }
            for record in logs
        ]
        try:
            await self.ocean.port_client.ingest_integration_logs(raw_logs)
        except Exception as e:
            logger.debug(f"Failed to send logs to Port: {e}")
