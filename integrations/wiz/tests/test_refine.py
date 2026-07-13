import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from wiz.options import ParallelismConfig
from wiz.pagination import (
    PaginationPartition,
    PartitionRefiner,
    PartitionSplitter,
    ReadyPartitionCrawlStream,
)


def _parallelism_config(**overrides: Any) -> ParallelismConfig:
    config: dict[str, Any] = {
        "strategy": "auto",
        "date_interval_days": 30,
        "lookback_days": 365,
    }
    config.update(overrides)
    return config  # type: ignore[return-value]


async def _collect_ready_partitions(
    refiner: PartitionRefiner,
    resource: str,
    base_variables: dict[str, Any],
    partitions: list[PaginationPartition],
    config: ParallelismConfig,
) -> list[PaginationPartition]:
    return [
        partition
        async for partition in refiner.iter_ready_partitions(
            resource, base_variables, partitions, config
        )
    ]


def test_bisect_date_partition_splits_window_in_half() -> None:
    splitter = PartitionSplitter()
    partition = PaginationPartition(
        label="vulnerabilityFindings-date-1",
        filter_overlay={
            "firstSeenAt": {
                "after": "2026-01-01T00:00:00Z",
                "before": "2026-02-01T00:00:00Z",
            }
        },
    )

    children = splitter.bisect_date_partition(partition)

    assert children is not None
    assert len(children) == 2
    assert children[0].filter_overlay["firstSeenAt"]["after"] == "2026-01-01T00:00:00Z"
    assert children[0].filter_overlay["firstSeenAt"]["before"] == "2026-01-16T12:00:00Z"
    assert children[1].filter_overlay["firstSeenAt"]["after"] == "2026-01-16T12:00:00Z"
    assert children[1].filter_overlay["firstSeenAt"]["before"] == "2026-02-01T00:00:00Z"


def test_bisect_date_partition_preserves_other_overlay_fields() -> None:
    splitter = PartitionSplitter()
    partition = PaginationPartition(
        label="vulnerabilityFindings-severity-critical",
        filter_overlay={
            "severity": ["CRITICAL"],
            "firstSeenAt": {
                "after": "2026-01-01T00:00:00Z",
                "before": "2026-02-01T00:00:00Z",
            },
        },
    )

    children = splitter.bisect_date_partition(partition)

    assert children is not None
    assert all(child.filter_overlay["severity"] == ["CRITICAL"] for child in children)


def test_split_partition_adds_date_windows_for_severity_partition() -> None:
    splitter = PartitionSplitter()
    partition = PaginationPartition(
        label="vulnerabilityFindings-severity-critical",
        filter_overlay={"severity": ["CRITICAL"]},
    )

    children = splitter.split(
        partition, _parallelism_config(lookback_days=60, date_interval_days=30)
    )

    assert len(children) == 2
    assert all("firstSeenAt" in child.filter_overlay for child in children)
    assert all(child.filter_overlay["severity"] == ["CRITICAL"] for child in children)


@pytest.mark.asyncio
async def test_refine_partitions_skips_empty_partitions() -> None:
    client = AsyncMock()
    client.get_resource_total_count = AsyncMock(return_value=0)
    partitions = [
        PaginationPartition(label="partition-a", filter_overlay={"severity": ["CRITICAL"]}),
        PaginationPartition(label="partition-b", filter_overlay={"severity": ["HIGH"]}),
    ]

    refined = await _collect_ready_partitions(
        PartitionRefiner(client),
        "vulnerabilityFindings",
        {"first": 100, "filterBy": {}},
        partitions,
        _parallelism_config(),
    )

    assert refined == []
    assert client.get_resource_total_count.await_count == 2


@pytest.mark.asyncio
async def test_refine_partitions_keeps_partitions_within_limit() -> None:
    client = AsyncMock()
    client.get_resource_total_count = AsyncMock(return_value=250)
    partition = PaginationPartition(
        label="partition-a",
        filter_overlay={"severity": ["CRITICAL"]},
    )

    refined = await _collect_ready_partitions(
        PartitionRefiner(
            client,
            max_entities=PartitionRefiner.DEFAULT_MAX_PARTITION_ENTITIES,
        ),
        "vulnerabilityFindings",
        {"first": 100, "filterBy": {}},
        [partition],
        _parallelism_config(),
    )

    assert refined == [partition]


@pytest.mark.asyncio
async def test_refine_partitions_splits_large_date_partition() -> None:
    client = AsyncMock()
    client.get_resource_total_count = AsyncMock(
        side_effect=[900, 400, 350],
    )
    partition = PaginationPartition(
        label="vulnerabilityFindings-date-1",
        filter_overlay={
            "firstSeenAt": {
                "after": "2026-01-01T00:00:00Z",
                "before": "2026-02-01T00:00:00Z",
            }
        },
    )

    refined = await _collect_ready_partitions(
        PartitionRefiner(client, max_entities=500),
        "vulnerabilityFindings",
        {"first": 100, "filterBy": {}},
        [partition],
        _parallelism_config(),
    )

    assert len(refined) == 2
    assert {child.label for child in refined} == {
        "vulnerabilityFindings-date-1-1",
        "vulnerabilityFindings-date-1-2",
    }


@pytest.mark.asyncio
async def test_refine_partitions_splits_severity_partition_with_date_subwindows() -> None:
    client = AsyncMock()
    client.get_resource_total_count = AsyncMock(
        side_effect=[1200, 300, 400],
    )
    partition = PaginationPartition(
        label="vulnerabilityFindings-severity-critical",
        filter_overlay={"severity": ["CRITICAL"]},
    )

    refined = await _collect_ready_partitions(
        PartitionRefiner(client, max_entities=500),
        "vulnerabilityFindings",
        {"first": 100, "filterBy": {}},
        [partition],
        _parallelism_config(lookback_days=60, date_interval_days=30),
    )

    assert len(refined) == 2
    assert all("firstSeenAt" in child.filter_overlay for child in refined)
    assert all(child.filter_overlay["severity"] == ["CRITICAL"] for child in refined)


@pytest.mark.asyncio
async def test_ready_partition_crawl_stream_starts_before_all_partitions_ready() -> None:
    release_second_probe = asyncio.Event()
    high_probe_waiting = asyncio.Event()
    crawl_started = asyncio.Event()

    class CountClient:
        async def get_resource_total_count(
            self, resource: str, variables: dict[str, Any]
        ) -> int:
            severity = (variables.get("filterBy") or {}).get("severity", [""])[0]
            if severity == "HIGH":
                high_probe_waiting.set()
                await release_second_probe.wait()
            return 100

    async def fetch_chain(
        resource: str,
        variables: dict[str, Any],
        max_pages: int | None,
        partition_label: str | None,
    ):
        crawl_started.set()
        yield [{"id": partition_label}]

    partitions = [
        PaginationPartition(
            label="severity-critical",
            filter_overlay={"severity": ["CRITICAL"]},
        ),
        PaginationPartition(
            label="severity-high",
            filter_overlay={"severity": ["HIGH"]},
        ),
    ]

    stream = ReadyPartitionCrawlStream(
        CountClient(),
        "vulnerabilityFindings",
        {"first": 100, "filterBy": {}},
        partitions,
        _parallelism_config(),
        fetch_chain,
    )

    consumer = asyncio.create_task(_collect_async_iterator(stream))

    await asyncio.wait_for(crawl_started.wait(), timeout=1)
    assert high_probe_waiting.is_set()
    assert not release_second_probe.is_set()

    release_second_probe.set()
    results = await consumer

    assert len(results) == 2


async def _collect_async_iterator(stream: ReadyPartitionCrawlStream) -> list[Any]:
    items: list[Any] = []
    async for item in stream:
        items.append(item)
    return items
