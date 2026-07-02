"""Structured logging for incremental sync observability.

Emits stable log event names intended for log-based metrics and alerting:
``incremental_sync_kind_completed`` and ``incremental_sync_run_completed``.
"""

from __future__ import annotations

import signal
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from loguru import logger

from port_ocean.helpers.monitor.models import ResourceUsageStats

_kind_resource_stats: ContextVar[KindResourceStats | None] = ContextVar(
    "incremental_kind_resource_stats", default=None
)

_previous_sigterm_handler: Any = None


@dataclass
class KindResourceStats:
    api_calls: int = 0
    cpu_max_percent: float = 0.0
    memory_max_bytes: int = 0

    @classmethod
    def from_usage_stats(cls, usage: ResourceUsageStats) -> "KindResourceStats":
        """Build incremental observability stats from monitor usage data."""
        return cls(
            api_calls=usage.request_count,
            cpu_max_percent=usage.cpu.cpu_max,
            memory_max_bytes=usage.memory.memory_max,
        )


@dataclass
class KindSyncOutcome:
    success: bool
    kind: str
    index: int
    items_fetched: int = 0
    api_calls: int = 0
    duration_seconds: float = 0.0
    cpu_max_percent: float = 0.0
    memory_max_bytes: int = 0
    cursor_before: datetime | None = None
    cursor_after: datetime | None = None
    cursor_source: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class IncrementalRunAccumulator:
    interval_seconds: int
    kinds_total: int
    kinds_succeeded: int = 0
    kinds_failed: int = 0
    items_fetched_total: int = 0
    api_calls_total: int = 0
    cursor_age_max_seconds: float = 0.0
    cpu_max_percent: float = 0.0
    memory_max_bytes: int = 0
    tick_loops: int = 0
    interrupted: bool = False
    status: str = "success"
    failed_kind: str | None = None

    def record_cursor_age(self, cursor: datetime, now: datetime) -> None:
        age_seconds = max(0.0, (now - cursor).total_seconds())
        self.cursor_age_max_seconds = max(self.cursor_age_max_seconds, age_seconds)

    def record_kind_success(self, outcome: KindSyncOutcome) -> None:
        self.kinds_succeeded += 1
        self.items_fetched_total += outcome.items_fetched
        self.api_calls_total += outcome.api_calls
        self.cpu_max_percent = max(self.cpu_max_percent, outcome.cpu_max_percent)
        self.memory_max_bytes = max(self.memory_max_bytes, outcome.memory_max_bytes)

    def record_kind_failure(self, outcome: KindSyncOutcome) -> None:
        self.kinds_failed += 1
        self.status = "failed"
        self.failed_kind = outcome.kind
        self.items_fetched_total += outcome.items_fetched
        self.api_calls_total += outcome.api_calls
        self.cpu_max_percent = max(self.cpu_max_percent, outcome.cpu_max_percent)
        self.memory_max_bytes = max(self.memory_max_bytes, outcome.memory_max_bytes)


def set_kind_resource_stats(stats: KindResourceStats) -> None:
    _kind_resource_stats.set(stats)


def get_kind_resource_stats() -> KindResourceStats | None:
    return _kind_resource_stats.get()


def clear_kind_resource_stats() -> None:
    _kind_resource_stats.set(None)


def install_interrupt_handler(on_interrupt: Callable[[], None]) -> None:
    global _previous_sigterm_handler

    def handler(signum: int, frame: object | None) -> None:
        on_interrupt()

    _previous_sigterm_handler = signal.signal(signal.SIGTERM, handler)


def remove_interrupt_handler() -> None:
    global _previous_sigterm_handler
    if _previous_sigterm_handler is not None:
        signal.signal(signal.SIGTERM, _previous_sigterm_handler)
        _previous_sigterm_handler = None


def log_incremental_kind_failure(
    kind: str,
    *,
    integration_id: str,
    errors: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Log a per-kind incremental failure without advancing the cursor."""
    logger.error(
        "Incremental sync failed — cursor not updated, next run will retry",
        kind=kind,
        integration_id=integration_id,
        errors=errors,
        error=error,
    )


def log_incremental_kind_completed(outcome: KindSyncOutcome) -> None:
    status = "success" if outcome.success else "failed"
    logger.info(
        "incremental_sync_kind_completed",
        kind=outcome.kind,
        index=outcome.index,
        status=status,
        items_fetched=outcome.items_fetched,
        api_calls=outcome.api_calls,
        duration_seconds=round(outcome.duration_seconds, 3),
        cpu_max_percent=round(outcome.cpu_max_percent, 2),
        memory_max_bytes=outcome.memory_max_bytes,
        cursor_before=(
            outcome.cursor_before.isoformat() if outcome.cursor_before else None
        ),
        cursor_after=(
            outcome.cursor_after.isoformat() if outcome.cursor_after else None
        ),
        cursor_source=outcome.cursor_source,
        errors=outcome.errors or None,
    )


def log_incremental_run_completed(
    accumulator: IncrementalRunAccumulator,
    *,
    duration_seconds: float,
    integration_id: str,
    integration_type: str,
) -> None:
    status = accumulator.status
    if accumulator.interrupted and status == "success":
        status = "interrupted"

    logger.info(
        "incremental_sync_run_completed",
        integration_id=integration_id,
        integration_type=integration_type,
        status=status,
        duration_seconds=round(duration_seconds, 3),
        interval_seconds=accumulator.interval_seconds,
        kinds_total=accumulator.kinds_total,
        kinds_succeeded=accumulator.kinds_succeeded,
        kinds_failed=accumulator.kinds_failed,
        failed_kind=accumulator.failed_kind,
        items_fetched_total=accumulator.items_fetched_total,
        api_calls_total=accumulator.api_calls_total,
        cursor_age_max_seconds=round(accumulator.cursor_age_max_seconds, 3),
        cpu_max_percent=round(accumulator.cpu_max_percent, 2),
        memory_max_bytes=accumulator.memory_max_bytes,
        tick_loops=accumulator.tick_loops,
        interrupted=accumulator.interrupted,
    )
