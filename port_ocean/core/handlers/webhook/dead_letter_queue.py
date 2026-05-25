import asyncio
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.helpers.metric.metric import MetricType


_SLUG_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_LAST_ERROR_MAX_CHARS = 500
_ENTRY_FILE_SUFFIX = ".json"


def _path_to_slug(path: str) -> str:
    slug = _SLUG_PATTERN.sub("_", path).strip("_")
    return slug or "root"


def _emit_metric(name: str, labels: List[str], value: float, op: str = "inc") -> None:
    """Emit a Prometheus metric; swallow errors if Ocean context isn't initialized (tests)."""
    try:
        from port_ocean.context.ocean import ocean

        result = (
            ocean.metrics.set_metric(name, labels, value)
            if op == "set"
            else ocean.metrics.inc_metric(name, labels, value)
        )
        if asyncio.iscoroutine(result):
            result.close()
    except Exception:
        pass


@dataclass
class DLQEntry:
    trace_id: str
    path: str
    event: WebhookEvent
    first_failed_at: datetime
    attempts: int
    next_retry_at: datetime
    last_error: str
    in_flight: bool = field(default=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "path": self.path,
            "event": self.event.to_dict(),
            "first_failed_at": self.first_failed_at.isoformat(),
            "attempts": self.attempts,
            "next_retry_at": self.next_retry_at.isoformat(),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DLQEntry":
        return cls(
            trace_id=data["trace_id"],
            path=data["path"],
            event=WebhookEvent.from_dict(data["event"]),
            first_failed_at=datetime.fromisoformat(data["first_failed_at"]),
            attempts=data["attempts"],
            next_retry_at=datetime.fromisoformat(data["next_retry_at"]),
            last_error=data["last_error"],
            in_flight=False,
        )


class DiskBackedDeadLetterQueue:
    """Per-path DLQ. Failed events are persisted to disk and replayed before new events.

    Backoff is exponential capped at ``max_backoff_seconds``; entries older than
    ``max_age_seconds`` (measured from first failure) are disposed on the next access.
    """

    def __init__(
        self,
        path: str,
        storage_path: str,
        max_age_seconds: float,
        initial_backoff_seconds: float,
        max_backoff_seconds: float,
        backoff_multiplier: float,
        max_entries: int,
    ) -> None:
        self._path = path
        self._max_age_seconds = max_age_seconds
        self._initial_backoff_seconds = initial_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._backoff_multiplier = backoff_multiplier
        self._max_entries = max_entries
        self._dir = Path(storage_path) / _path_to_slug(path)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, DLQEntry] = {}
        self._lock = asyncio.Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        for f in self._dir.glob(f"*{_ENTRY_FILE_SUFFIX}"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                entry = DLQEntry.from_dict(data)
                self._entries[entry.trace_id] = entry
            except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
                logger.warning(f"Failed to load DLQ entry {f}: {e}")

    def _entry_path(self, trace_id: str) -> Path:
        return self._dir / f"{trace_id}{_ENTRY_FILE_SUFFIX}"

    def _persist(self, entry: DLQEntry) -> None:
        target = self._entry_path(entry.trace_id)
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._dir,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                json.dump(entry.to_dict(), tmp)
                tmp_name = tmp.name
            os.replace(tmp_name, target)
        except (TypeError, ValueError, OSError) as e:
            logger.warning(f"Failed to persist DLQ entry {entry.trace_id}: {e}")

    def _remove_file(self, trace_id: str) -> None:
        target = self._entry_path(trace_id)
        try:
            target.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Failed to remove DLQ entry file {target}: {e}")

    def _compute_next_retry_at(self, attempts: int, now: datetime) -> datetime:
        delay = min(
            self._initial_backoff_seconds * (self._backoff_multiplier**attempts),
            self._max_backoff_seconds,
        )
        return now + timedelta(seconds=delay)

    def _dispose_expired_locked(self) -> List[str]:
        now = datetime.now(timezone.utc)
        expired = [
            t
            for t, e in self._entries.items()
            if (now - e.first_failed_at).total_seconds() > self._max_age_seconds
            and not e.in_flight
        ]
        for trace_id in expired:
            self._remove_file(trace_id)
            self._entries.pop(trace_id, None)
        if expired:
            _emit_metric(
                MetricType.DLQ_ENTRIES_DISPOSED_NAME, [self._path], len(expired)
            )
            _emit_metric(
                MetricType.DLQ_SIZE_NAME, [self._path], len(self._entries), op="set"
            )
        return expired

    def _evict_oldest_locked(self) -> None:
        evictable = [e for e in self._entries.values() if not e.in_flight]
        if not evictable:
            return
        victim = min(evictable, key=lambda e: e.first_failed_at)
        self._entries.pop(victim.trace_id, None)
        self._remove_file(victim.trace_id)
        logger.warning(
            "Evicted oldest DLQ entry due to max_entries cap",
            trace_id=victim.trace_id,
            path=self._path,
            attempts=victim.attempts,
            age_seconds=(
                datetime.now(timezone.utc) - victim.first_failed_at
            ).total_seconds(),
        )
        _emit_metric(MetricType.DLQ_ENTRIES_EVICTED_NAME, [self._path], 1)

    async def add(self, event: WebhookEvent, error: str) -> Optional[DLQEntry]:
        now = datetime.now(timezone.utc)
        async with self._lock:
            existing = self._entries.get(event.trace_id)
            attempts = 0 if existing is None else existing.attempts + 1
            first_failed_at = existing.first_failed_at if existing is not None else now
            if (now - first_failed_at).total_seconds() > self._max_age_seconds:
                if existing is not None:
                    self._entries.pop(event.trace_id, None)
                    self._remove_file(event.trace_id)
                logger.warning(
                    "Discarding DLQ entry past max_age",
                    trace_id=event.trace_id,
                    path=self._path,
                    attempts=attempts,
                )
                return None
            if existing is None and len(self._entries) >= self._max_entries:
                self._evict_oldest_locked()
            entry = DLQEntry(
                trace_id=event.trace_id,
                path=self._path,
                event=event.clone(),
                first_failed_at=first_failed_at,
                attempts=attempts,
                next_retry_at=self._compute_next_retry_at(attempts, now),
                last_error=error[:_LAST_ERROR_MAX_CHARS],
                in_flight=False,
            )
            self._entries[entry.trace_id] = entry
            self._persist(entry)
            _emit_metric(MetricType.DLQ_ENTRIES_ADDED_NAME, [self._path], 1)
            _emit_metric(
                MetricType.DLQ_SIZE_NAME, [self._path], len(self._entries), op="set"
            )
            return entry

    async def try_pop_ready(self) -> Optional[DLQEntry]:
        async with self._lock:
            self._dispose_expired_locked()
            candidates = [e for e in self._entries.values() if not e.in_flight]
            if not candidates:
                return None
            soonest = min(candidates, key=lambda e: e.next_retry_at)
            if soonest.next_retry_at > datetime.now(timezone.utc):
                return None
            soonest.in_flight = True
            _emit_metric(MetricType.DLQ_ENTRIES_REPLAYED_NAME, [self._path], 1)
            return soonest

    async def mark_succeeded(self, trace_id: str) -> None:
        async with self._lock:
            existed = self._entries.pop(trace_id, None) is not None
            self._remove_file(trace_id)
            if existed:
                _emit_metric(MetricType.DLQ_ENTRIES_COMPLETED_NAME, [self._path], 1)
                _emit_metric(
                    MetricType.DLQ_SIZE_NAME,
                    [self._path],
                    len(self._entries),
                    op="set",
                )

    async def release_in_flight(self, trace_id: str) -> None:
        """Return a popped-but-unprocessed entry to the queue (e.g., on shutdown)."""
        async with self._lock:
            entry = self._entries.get(trace_id)
            if entry is not None:
                entry.in_flight = False

    async def seconds_until_next_ready(self) -> Optional[float]:
        async with self._lock:
            self._dispose_expired_locked()
            now = datetime.now(timezone.utc)
            pending = [e for e in self._entries.values() if not e.in_flight]
            if not pending:
                return None
            soonest = min(e.next_retry_at for e in pending)
            return max(0.0, (soonest - now).total_seconds())

    async def size(self) -> int:
        async with self._lock:
            return len(self._entries)
