import copy
import datetime
from typing import Any

from wiz.pagination.base import PaginationPartition


def generate_date_windows(
    lookback_days: int,
    interval_days: int,
    now: datetime.datetime | None = None,
) -> list[tuple[datetime.datetime, datetime.datetime]]:
    current_time = now or datetime.datetime.now(datetime.UTC)
    start_time = current_time - datetime.timedelta(days=lookback_days)
    interval = datetime.timedelta(days=interval_days)

    windows: list[tuple[datetime.datetime, datetime.datetime]] = []
    window_start = start_time
    while window_start < current_time:
        window_end = min(window_start + interval, current_time)
        windows.append((window_start, window_end))
        window_start = window_end

    return windows


def to_iso8601(timestamp: datetime.datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.UTC)
    else:
        timestamp = timestamp.astimezone(datetime.UTC)
    return timestamp.isoformat().replace("+00:00", "Z")


def merge_partition_filters(
    variables: dict[str, Any], partition: PaginationPartition
) -> dict[str, Any]:
    merged_variables = copy.deepcopy(variables)
    filter_by = merged_variables.setdefault("filterBy", {})
    for key, value in partition.filter_overlay.items():
        if isinstance(value, dict) and isinstance(filter_by.get(key), dict):
            filter_by[key] = {**filter_by[key], **value}
        else:
            filter_by[key] = value
    merged_variables.pop("after", None)
    return merged_variables


def build_date_partitions(
    resource_label: str,
    date_field: str,
    lookback_days: int,
    interval_days: int,
) -> list[PaginationPartition]:
    partitions: list[PaginationPartition] = []
    for index, (window_start, window_end) in enumerate(
        generate_date_windows(
            lookback_days=lookback_days,
            interval_days=interval_days,
        ),
        start=1,
    ):
        date_filter = {
            "after": to_iso8601(window_start),
            "before": to_iso8601(window_end),
        }
        partitions.append(
            PaginationPartition(
                label=f"{resource_label}-date-{index}",
                filter_overlay={
                    date_field: date_filter,
                },
            )
        )
    return partitions
