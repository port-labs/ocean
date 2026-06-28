from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from port_ocean.config.settings import LiveEventsRedisSettings

_PEL_CONSUMER_NAME = "pel-requeue-worker"


@dataclass(frozen=True)
class PELRequeueWorkerSettings:
    stream_key: str
    consumer_group: str
    stuck_timeout_ms: int = 60_000
    max_requeue_count: int = 3
    scan_interval_seconds: float = 30.0
    xautoclaim_count: int = 100
    lifecycle_error_backoff_seconds: float = 5.0

    @classmethod
    def from_live_events_redis_settings(
        cls,
        redis_settings: "LiveEventsRedisSettings",
        *,
        stream_key: str,
        consumer_group: str,
    ) -> "PELRequeueWorkerSettings":
        return cls(
            stream_key=stream_key,
            consumer_group=consumer_group,
            stuck_timeout_ms=redis_settings.pel_stuck_timeout_seconds * 1000,
            max_requeue_count=redis_settings.pel_max_requeue_count,
            scan_interval_seconds=float(redis_settings.pel_scan_interval_seconds),
            xautoclaim_count=redis_settings.pel_xautoclaim_count,
            lifecycle_error_backoff_seconds=float(
                redis_settings.pel_lifecycle_error_backoff_seconds
            ),
        )
