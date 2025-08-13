import os
from typing import Any, AsyncGenerator
import uuid

import aiofiles
import httpx
import ijson  # type: ignore[import-untyped]
from cryptography.fernet import Fernet

import port_ocean.context.ocean as ocean_context


class Stream:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.headers = response.headers
        self.status_code = response.status_code

    async def _byte_stream(
        self, chunk_size: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        if chunk_size is None:
            chunk_size = ocean_context.ocean.config.streaming.chunk_size

        file_name = f"{ocean_context.ocean.config.streaming.location}/{uuid.uuid4()}"

        crypt = Fernet(Fernet.generate_key())

        try:
            async for chunk in self.response.aiter_bytes(chunk_size=chunk_size):
                async with aiofiles.open(f"{file_name}", "ab") as f:
                    if len(chunk) > 0:
                        await f.write(crypt.encrypt(chunk))
                        await f.write(b"\n")
        finally:
            await self.response.aclose()

        try:
            async with aiofiles.open(f"{file_name}", mode="rb") as f:
                while True:
                    line = await f.readline()
                    if not line:
                        break
                    data = crypt.decrypt(line)
                    yield data
        finally:
            try:
                os.remove(file_name)
            except FileNotFoundError:
                pass

    async def get_json_stream(
        self,
        target_items: str = "",
        max_buffer_size_mb: int | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if max_buffer_size_mb is None:
            max_buffer_size_mb = ocean_context.ocean.config.streaming.max_buffer_size_mb

        events = ijson.sendable_list()
        coro = ijson.items_coro(events, target_items)
        current_buffer_size = 0
        async for chunk in self._byte_stream():
            coro.send(chunk)
            current_buffer_size += len(chunk)
            if current_buffer_size >= max_buffer_size_mb:
                if len(events) > 0:
                    yield events
                    events.clear()
                    current_buffer_size = 0
        yield events
