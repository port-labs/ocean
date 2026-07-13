import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from loguru import logger
from port_ocean.utils.async_iterators import stream_independent_async_iterators

from wiz.options import ParallelismConfig

from .base import PaginationPartition
from .utils import build_date_partitions, merge_partition_filters, to_iso8601

DEFAULT_MAX_PARTITION_ENTITIES = 500
MIN_DATE_WINDOW = datetime.timedelta(seconds=1)


class ResourceCountClient(Protocol):
    async def get_resource_total_count(
        self, resource: str, variables: dict[str, Any]
    ) -> int: ...


def parse_iso8601(value: str) -> datetime.datetime:
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.UTC)
    return parsed.astimezone(datetime.UTC)


def bisect_date_partition(
    partition: PaginationPartition,
) -> list[PaginationPartition] | None:
    date_filter = partition.filter_overlay.get("firstSeenAt")
    if not isinstance(date_filter, dict):
        return None

    after_raw = date_filter.get("after")
    before_raw = date_filter.get("before")
    if not isinstance(after_raw, str) or not isinstance(before_raw, str):
        return None

    window_start = parse_iso8601(after_raw)
    window_end = parse_iso8601(before_raw)
    if window_end - window_start <= MIN_DATE_WINDOW:
        return None

    midpoint = window_start + (window_end - window_start) / 2
    base_overlay = {
        key: value
        for key, value in partition.filter_overlay.items()
        if key != "firstSeenAt"
    }

    return [
        PaginationPartition(
            label=f"{partition.label}-1",
            filter_overlay={
                **base_overlay,
                "firstSeenAt": {
                    "after": to_iso8601(window_start),
                    "before": to_iso8601(midpoint),
                },
            },
        ),
        PaginationPartition(
            label=f"{partition.label}-2",
            filter_overlay={
                **base_overlay,
                "firstSeenAt": {
                    "after": to_iso8601(midpoint),
                    "before": to_iso8601(window_end),
                },
            },
        ),
    ]


def split_partition(
    partition: PaginationPartition,
    config: ParallelismConfig,
) -> list[PaginationPartition]:
    if "firstSeenAt" in partition.filter_overlay:
        bisected = bisect_date_partition(partition)
        return bisected or []

    lookback_days = config.get("lookback_days")
    if lookback_days is None or lookback_days <= 0:
        lookback_days = 365

    date_partitions = build_date_partitions(
        resource_label=partition.label,
        date_field="firstSeenAt",
        lookback_days=lookback_days,
        interval_days=config["date_interval_days"],
    )
    if len(date_partitions) <= 1:
        return []

    base_overlay = {
        key: value
        for key, value in partition.filter_overlay.items()
        if key != "firstSeenAt"
    }
    return [
        PaginationPartition(
            label=date_partition.label,
            filter_overlay={**base_overlay, **date_partition.filter_overlay},
        )
        for date_partition in date_partitions
    ]


async def _refine_partition_streaming(
    client: ResourceCountClient,
    resource: str,
    base_variables: dict[str, Any],
    partition: PaginationPartition,
    config: ParallelismConfig,
    max_entities: int,
) -> AsyncIterator[PaginationPartition]:
    variables = merge_partition_filters(base_variables, partition)
    count = await client.get_resource_total_count(resource, variables)

    if count == 0:
        logger.info(f"Skipping empty partition {partition.label}")
        return

    if count <= max_entities:
        logger.info(
            f"Partition {partition.label} has {count} entities (within limit of {max_entities})"
        )
        yield partition
        return

    logger.info(
        f"Partition {partition.label} has {count} entities, splitting (limit {max_entities})"
    )
    children = split_partition(partition, config)
    if not children:
        logger.warning(
            f"Cannot split partition {partition.label} further ({count} entities), keeping as-is"
        )
        yield partition
        return

    async for ready_partition in stream_independent_async_iterators(
        *[
            _refine_partition_streaming(
                client,
                resource,
                base_variables,
                child,
                config,
                max_entities,
            )
            for child in children
        ],
        context=f"refine {partition.label}",
    ):
        yield ready_partition


async def iter_ready_partitions(
    client: ResourceCountClient,
    resource: str,
    base_variables: dict[str, Any],
    partitions: list[PaginationPartition],
    config: ParallelismConfig,
    max_entities: int = DEFAULT_MAX_PARTITION_ENTITIES,
) -> AsyncIterator[PaginationPartition]:
    if not partitions:
        return

    async for ready_partition in stream_independent_async_iterators(
        *[
            _refine_partition_streaming(
                client,
                resource,
                base_variables,
                partition,
                config,
                max_entities,
            )
            for partition in partitions
        ],
        context="partition refinement",
    ):
        yield ready_partition


_CRAWL_STREAM_DONE = object()


async def stream_ready_partition_crawls(
    client: ResourceCountClient,
    resource: str,
    base_variables: dict[str, Any],
    initial_partitions: list[PaginationPartition],
    config: ParallelismConfig,
    fetch_chain: Callable[..., AsyncIterator[list[Any]]],
    max_pages: int | None = None,
    max_entities: int = DEFAULT_MAX_PARTITION_ENTITIES,
) -> AsyncIterator[list[Any]]:
    result_queue: asyncio.Queue[Any] = asyncio.Queue()
    active_crawls = 0
    refinement_complete = False
    ready_count = 0

    async def mark_crawl_finished() -> None:
        nonlocal active_crawls
        active_crawls -= 1
        if refinement_complete and active_crawls == 0:
            await result_queue.put(_CRAWL_STREAM_DONE)

    async def crawl_partition(partition: PaginationPartition) -> None:
        nonlocal active_crawls
        active_crawls += 1
        try:
            variables = merge_partition_filters(base_variables, partition)
            async for batch in fetch_chain(
                resource, variables, max_pages, partition.label
            ):
                await result_queue.put(batch)
        except Exception as exc:
            await result_queue.put(exc)
        finally:
            await mark_crawl_finished()

    async def refine_and_launch() -> None:
        nonlocal refinement_complete, ready_count
        try:
            async for partition in iter_ready_partitions(
                client,
                resource,
                base_variables,
                initial_partitions,
                config,
                max_entities,
            ):
                ready_count += 1
                asyncio.create_task(crawl_partition(partition))
        except Exception as exc:
            await result_queue.put(exc)
        finally:
            refinement_complete = True
            logger.info(
                f"Partition refinement finished with {ready_count} crawl partitions "
                f"launched from {len(initial_partitions)} initial partitions"
            )
            if active_crawls == 0:
                await result_queue.put(_CRAWL_STREAM_DONE)

    refine_task = asyncio.create_task(refine_and_launch())

    try:
        while True:
            item = await result_queue.get()
            if item is _CRAWL_STREAM_DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        if not refine_task.done():
            refine_task.cancel()
        await asyncio.gather(refine_task, return_exceptions=True)


async def refine_partitions(
    client: ResourceCountClient,
    resource: str,
    base_variables: dict[str, Any],
    partitions: list[PaginationPartition],
    config: ParallelismConfig,
    max_entities: int = DEFAULT_MAX_PARTITION_ENTITIES,
) -> list[PaginationPartition]:
    refined_partitions = [
        partition
        async for partition in iter_ready_partitions(
            client,
            resource,
            base_variables,
            partitions,
            config,
            max_entities,
        )
    ]

    logger.info(
        f"Refined {len(partitions)} initial partitions into {len(refined_partitions)} crawl partitions"
    )
    return refined_partitions
