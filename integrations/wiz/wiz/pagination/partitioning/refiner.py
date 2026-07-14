from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from loguru import logger
from port_ocean.utils.async_iterators import stream_independent_async_iterators

from wiz.options import ParallelismConfig

from wiz.pagination.base import PaginationPartition
from wiz.pagination.utils import merge_partition_filters
from wiz.pagination.partitioning.splitter import PartitionSplitter

if TYPE_CHECKING:
    from wiz.client import WizClient


class PartitionRefiner:
    def __init__(self, client: WizClient, config: ParallelismConfig) -> None:
        self._client = client
        self._config = config
        self._splitter = PartitionSplitter()

    async def iter_ready_partitions(
        self,
        resource: str,
        base_variables: dict[str, Any],
        partitions: list[PaginationPartition],
        config: ParallelismConfig,
    ) -> AsyncIterator[PaginationPartition]:
        if not partitions:
            return

        async for ready_partition in stream_independent_async_iterators(
            *[
                self._refine_partition_streaming(
                    resource, base_variables, partition, config
                )
                for partition in partitions
            ],
            context="partition refinement",
        ):
            yield ready_partition

    async def _refine_partition_streaming(
        self,
        resource: str,
        base_variables: dict[str, Any],
        partition: PaginationPartition,
        config: ParallelismConfig,
    ) -> AsyncIterator[PaginationPartition]:
        variables = merge_partition_filters(base_variables, partition)
        count = await self._client.get_resource_total_count(resource, variables)

        if count == 0:
            logger.info(f"Skipping empty partition {partition.label}")
            return

        max_entities = config.max_partition_entities
        if count <= max_entities:
            logger.info(
                f"Partition {partition.label} has {count} entities (within limit of {max_entities})"
            )
            yield partition
            return

        logger.info(
            f"Partition {partition.label} has {count} entities, splitting (limit {max_entities})"
        )
        children = self._splitter.split(partition, config)
        if not children:
            logger.warning(
                f"Cannot split partition {partition.label} further "
                f"({count} entities), keeping as-is"
            )
            yield partition
            return

        async for ready_partition in stream_independent_async_iterators(
            *[
                self._refine_partition_streaming(
                    resource, base_variables, child, config
                )
                for child in children
            ],
            context=f"refine {partition.label}",
        ):
            yield ready_partition
