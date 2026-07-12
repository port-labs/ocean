import datetime
from typing import Any, cast

from wiz.options import ParallelismConfig
from wiz.pagination import (
    PaginationPartition,
    VulnerabilityFindingPartitionStrategy,
    generate_date_windows,
    merge_partition_filters,
)


def _parallelism_config(**overrides: Any) -> ParallelismConfig:
    config: dict[str, Any] = {
        "max_concurrent": 10,
        "strategy": "auto",
        "date_interval_days": 30,
        "lookback_days": 365,
    }
    config.update(overrides)
    return cast(ParallelismConfig, config)


def test_generate_date_windows_creates_half_open_intervals() -> None:
    now = datetime.datetime(2026, 1, 31, tzinfo=datetime.UTC)
    windows = generate_date_windows(
        lookback_days=60,
        interval_days=30,
        now=now,
    )

    assert len(windows) == 2
    assert windows[0][0] == now - datetime.timedelta(days=60)
    assert windows[0][1] == now - datetime.timedelta(days=30)
    assert windows[1][0] == now - datetime.timedelta(days=30)
    assert windows[1][1] == now


def test_vulnerability_finding_strategy_uses_date_partitions_by_default() -> None:
    variables = {"first": 100, "filterBy": {"status": ["OPEN"]}}
    partitions = VulnerabilityFindingPartitionStrategy().build_partitions(
        "vulnerabilityFindings",
        variables,
        _parallelism_config(strategy="auto"),
    )

    assert len(partitions) > 1
    assert all("firstSeenAt" in partition.filter_overlay for partition in partitions)
    assert all("updatedAt" in partition.filter_overlay for partition in partitions)


def test_vulnerability_finding_strategy_skips_severity_when_already_filtered() -> None:
    variables = {
        "first": 100,
        "filterBy": {"severity": ["CRITICAL"]},
    }
    partitions = VulnerabilityFindingPartitionStrategy().build_partitions(
        "vulnerabilityFindings",
        variables,
        _parallelism_config(strategy="severity", lookback_days=None),
    )

    assert partitions == []


def test_vulnerability_finding_strategy_falls_back_to_severity_without_lookback() -> (
    None
):
    variables = {"first": 100, "filterBy": {}}
    partitions = VulnerabilityFindingPartitionStrategy().build_partitions(
        "vulnerabilityFindings",
        variables,
        _parallelism_config(strategy="auto", lookback_days=None),
    )

    assert len(partitions) == 5
    assert {partition.filter_overlay["severity"][0] for partition in partitions} == {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "NONE",
    }


def test_merge_partition_filters_deep_merges_filters_and_clears_cursor() -> None:
    variables = {
        "first": 100,
        "after": "cursor-1",
        "filterBy": {"status": ["OPEN"]},
    }
    partition = PaginationPartition(
        label="test-partition",
        filter_overlay={
            "firstSeenAt": {
                "after": "2026-01-01T00:00:00Z",
                "before": "2026-02-01T00:00:00Z",
            }
        },
    )

    merged = merge_partition_filters(variables, partition)

    assert "after" not in merged
    assert merged["filterBy"]["status"] == ["OPEN"]
    assert merged["filterBy"]["firstSeenAt"]["after"] == "2026-01-01T00:00:00Z"
    assert variables["after"] == "cursor-1"
