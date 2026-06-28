from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from port_ocean.config.settings import LiveEventsRedisSettings

_LEADER_KEY_SUFFIX = "pel-requeue:leader"
_PEL_CONSUMER_NAME = "pel-requeue-worker"
_PEL_LEADER_ELECTION_NAME = "PEL requeue"


@dataclass(frozen=True)
class PELRequeueWorkerSettings:
    stream_key: str
    consumer_group: str
    pod_id: str
    stuck_timeout_ms: int = 60_000
    max_requeue_count: int = 3
    scan_interval_seconds: float = 30.0
    xautoclaim_count: int = 100
    leader_ttl_ms: int = 30_000
    leader_heartbeat_seconds: float = 10.0
    election_retry_seconds: float = 15.0
    lifecycle_error_backoff_seconds: float = 5.0

    @property
    def leader_key(self) -> str:
        return f"{self.stream_key}:{_LEADER_KEY_SUFFIX}"

    @classmethod
    def from_live_events_redis_settings(
        cls,
        redis_settings: "LiveEventsRedisSettings",
        *,
        stream_key: str,
        consumer_group: str,
        pod_id: str,
    ) -> "PELRequeueWorkerSettings":
        return cls(
            stream_key=stream_key,
            consumer_group=consumer_group,
            pod_id=pod_id,
            stuck_timeout_ms=redis_settings.pel_stuck_timeout_seconds * 1000,
            max_requeue_count=redis_settings.pel_max_requeue_count,
            scan_interval_seconds=float(redis_settings.pel_scan_interval_seconds),
            xautoclaim_count=redis_settings.pel_xautoclaim_count,
            leader_ttl_ms=redis_settings.leader_election_ttl_ms,
            leader_heartbeat_seconds=float(
                redis_settings.leader_election_heartbeat_seconds
            ),
            election_retry_seconds=float(redis_settings.leader_election_retry_seconds),
            lifecycle_error_backoff_seconds=float(
                redis_settings.pel_lifecycle_error_backoff_seconds
            ),
        )
