from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from loguru import logger

from wiz.options import ParallelismConfig

from wiz.pagination.base import PaginationPartition
from wiz.pagination.utils import merge_partition_filters
from wiz.pagination.partitioning.refiner import PartitionRefiner

if TYPE_CHECKING:
    from wiz.client import WizClient


class ReadyPartitionCrawlStream:
    _STREAM_DONE = object()

    def __init__(
        self,
        client: WizClient,
        resource: str,
        base_variables: dict[str, Any],
        initial_partitions: list[PaginationPartition],
        config: ParallelismConfig,
        get_resources: Callable[..., AsyncIterator[list[Any]]],
        max_pages: int | None = None,
    ) -> None:
        self._client = client
        self._resource = resource
        self._base_variables = base_variables
        self._initial_partitions = initial_partitions
        self._config = config
        self._get_resources = get_resources
        self._max_pages = max_pages
        self._refiner = PartitionRefiner(client, config)
        self._result_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._active_crawls = 0
        self._refinement_complete = False
        self._ready_count = 0
        self._refine_task: asyncio.Task[None] | None = None

    def __aiter__(self) -> AsyncIterator[list[Any]]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[list[Any]]:
        self._refine_task = asyncio.create_task(self._refine_and_launch())
        try:
            while True:
                item = await self._result_queue.get()
                if item is self._STREAM_DONE:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            if not self._refine_task:
                return
            if not self._refine_task.done():
                self._refine_task.cancel()
            await asyncio.gather(self._refine_task, return_exceptions=True)

    async def _mark_crawl_finished(self) -> None:
        self._active_crawls -= 1
        if self._refinement_complete and self._active_crawls == 0:
            logger.info(
                f"All partition crawls finished ({self._ready_count} crawls launched)"
            )
            await self._result_queue.put(self._STREAM_DONE)

    async def _crawl_partition(self, partition: PaginationPartition) -> None:
        self._active_crawls += 1
        try:
            variables = merge_partition_filters(self._base_variables, partition)
            async for batch in self._get_resources(
                self._resource,
                variables,
                self._max_pages,
                partition.label,
            ):
                await self._result_queue.put(batch)
        except Exception as exc:
            await self._result_queue.put(exc)
        finally:
            await self._mark_crawl_finished()

    async def _refine_and_launch(self) -> None:
        try:
            async for partition in self._refiner.iter_ready_partitions(
                self._resource,
                self._base_variables,
                self._initial_partitions,
                self._config,
            ):
                self._ready_count += 1
                asyncio.create_task(self._crawl_partition(partition))
        except Exception as exc:
            await self._result_queue.put(exc)
        finally:
            self._refinement_complete = True
            logger.info(
                f"Partition probe/split complete: launched {self._ready_count} crawls "
                f"from {len(self._initial_partitions)} initial partitions "
                f"({self._active_crawls} still running)"
            )
            if self._active_crawls == 0:
                await self._result_queue.put(self._STREAM_DONE)
