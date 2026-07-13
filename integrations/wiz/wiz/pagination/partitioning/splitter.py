import datetime

from wiz.options import ParallelismConfig

from wiz.pagination.base import PaginationPartition
from wiz.pagination.utils import build_date_partitions, to_iso8601


class PartitionSplitter:
    MIN_DATE_WINDOW = datetime.timedelta(seconds=1)

    @staticmethod
    def parse_iso8601(value: str) -> datetime.datetime:
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        parsed = datetime.datetime.fromisoformat(value)
        return parsed.replace(tzinfo=datetime.UTC) if parsed.tzinfo is None else parsed.astimezone(datetime.UTC)

    def bisect_date_partition(
        self, partition: PaginationPartition
    ) -> list[PaginationPartition] | None:
        date_filter = partition.filter_overlay.get("firstSeenAt")
        if not isinstance(date_filter, dict):
            return None

        after_raw = date_filter.get("after")
        before_raw = date_filter.get("before")
        if not isinstance(after_raw, str) or not isinstance(before_raw, str):
            return None

        window_start = self.parse_iso8601(after_raw)
        window_end = self.parse_iso8601(before_raw)
        if window_end - window_start <= self.MIN_DATE_WINDOW:
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

    def split(
        self, partition: PaginationPartition, config: ParallelismConfig
    ) -> list[PaginationPartition]:
        if "firstSeenAt" in partition.filter_overlay:
            bisected = self.bisect_date_partition(partition)
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
