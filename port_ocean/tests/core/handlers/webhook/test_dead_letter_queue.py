import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter

from port_ocean.config.settings import WebhookDeadLetterQueueSettings
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.dead_letter_queue import (
    DiskBackedDeadLetterQueue,
    _path_to_slug,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.exceptions.webhook_processor import (
    DeadLetterableError,
    RateLimitError,
)
from port_ocean.utils.signal import SignalHandler


def _event(trace_id: str = "trace-1") -> WebhookEvent:
    return WebhookEvent(trace_id=trace_id, payload={"k": "v"}, headers={"h": "1"})


def _dlq(
    tmp_path: Path,
    *,
    path: str = "/hook",
    max_age_seconds: float = 60.0,
    initial_backoff_seconds: float = 0.01,
    max_backoff_seconds: float = 0.5,
    backoff_multiplier: float = 2.0,
    max_entries: int = 1000,
) -> DiskBackedDeadLetterQueue:
    return DiskBackedDeadLetterQueue(
        path=path,
        storage_path=str(tmp_path),
        max_age_seconds=max_age_seconds,
        initial_backoff_seconds=initial_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        backoff_multiplier=backoff_multiplier,
        max_entries=max_entries,
    )


def test_path_to_slug_handles_unsafe_chars() -> None:
    assert _path_to_slug("/foo/bar") == "foo_bar"
    assert _path_to_slug("integration/webhook$1") == "integration_webhook_1"
    assert _path_to_slug("///") == "root"
    assert _path_to_slug("") == "root"


@pytest.mark.asyncio
async def test_add_persists_entry_to_disk(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path)
    entry = await dlq.add(_event("t1"), "RateLimitError: budget exceeded")
    assert entry is not None
    files = list(Path(tmp_path).rglob("*.json"))
    assert any(f.name == "t1.json" for f in files)
    assert await dlq.size() == 1


@pytest.mark.asyncio
async def test_entry_not_ready_during_backoff(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=10.0)
    await dlq.add(_event("t1"), "err")
    assert await dlq.try_pop_ready() is None
    secs = await dlq.seconds_until_next_ready()
    assert secs is not None and secs > 0


@pytest.mark.asyncio
async def test_entry_ready_after_backoff(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.01)
    await dlq.add(_event("t1"), "err")
    await asyncio.sleep(0.05)
    entry = await dlq.try_pop_ready()
    assert entry is not None
    assert entry.trace_id == "t1"
    assert entry.in_flight is True


@pytest.mark.asyncio
async def test_backoff_grows_on_re_add(tmp_path: Path) -> None:
    dlq = _dlq(
        tmp_path,
        initial_backoff_seconds=0.01,
        max_backoff_seconds=10.0,
        backoff_multiplier=2.0,
    )
    first = await dlq.add(_event("t1"), "err")
    assert first is not None and first.attempts == 0
    await asyncio.sleep(0.02)
    entry = await dlq.try_pop_ready()
    assert entry is not None
    second = await dlq.add(_event("t1"), "err")
    assert second is not None
    assert second.attempts == 1
    assert second.next_retry_at > first.next_retry_at


@pytest.mark.asyncio
async def test_entries_past_max_age_are_disposed(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, max_age_seconds=60)
    await dlq.add(_event("t1"), "err")
    entry = dlq._entries["t1"]
    entry.first_failed_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert await dlq.try_pop_ready() is None
    assert await dlq.size() == 0
    assert not (Path(tmp_path) / "hook" / "t1.json").exists()


@pytest.mark.asyncio
async def test_add_past_max_age_discards(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, max_age_seconds=0.001)
    first = await dlq.add(_event("t1"), "err")
    assert first is not None
    await asyncio.sleep(0.01)
    second = await dlq.add(_event("t1"), "err again")
    assert second is None
    assert await dlq.size() == 0


@pytest.mark.asyncio
async def test_mark_succeeded_removes_from_disk(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path)
    await dlq.add(_event("t1"), "err")
    assert (Path(tmp_path) / "hook" / "t1.json").exists()
    await dlq.mark_succeeded("t1")
    assert not (Path(tmp_path) / "hook" / "t1.json").exists()
    assert await dlq.size() == 0


@pytest.mark.asyncio
async def test_release_in_flight_returns_entry_to_pool(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.01)
    await dlq.add(_event("t1"), "err")
    await asyncio.sleep(0.02)
    entry = await dlq.try_pop_ready()
    assert entry is not None
    assert await dlq.try_pop_ready() is None
    await dlq.release_in_flight("t1")
    again = await dlq.try_pop_ready()
    assert again is not None and again.trace_id == "t1"


@pytest.mark.asyncio
async def test_metrics_are_emitted_for_add_pop_and_succeed(tmp_path: Path) -> None:
    metrics = MagicMock()
    metrics.inc_metric = MagicMock()
    metrics.set_metric = MagicMock()
    with patch("port_ocean.context.ocean.ocean") as ocean_mock:
        ocean_mock.metrics = metrics
        dlq = _dlq(tmp_path, initial_backoff_seconds=0.01)
        await dlq.add(_event("t1"), "RateLimitError")
        await asyncio.sleep(0.02)
        popped = await dlq.try_pop_ready()
        assert popped is not None
        await dlq.mark_succeeded("t1")

    inc_names = [c.args[0] for c in metrics.inc_metric.call_args_list]
    set_names = [c.args[0] for c in metrics.set_metric.call_args_list]
    assert "webhook_dlq_entries_added" in inc_names
    assert "webhook_dlq_entries_replayed" in inc_names
    assert "webhook_dlq_entries_completed" in inc_names
    assert "webhook_dlq_size" in set_names


@pytest.mark.asyncio
async def test_persisted_entries_are_valid_json(tmp_path: Path) -> None:
    import json as _json

    dlq = _dlq(tmp_path)
    event = WebhookEvent(
        trace_id="t-json",
        payload={"nested": {"x": 1, "y": [1, 2, 3]}},
        headers={"content-type": "application/json"},
        group_id="grp-1",
    )
    await dlq.add(event, "RateLimitError: budget exceeded")
    with open(Path(tmp_path) / "hook" / "t-json.json", "r", encoding="utf-8") as f:
        data = _json.load(f)
    assert data["trace_id"] == "t-json"
    assert data["event"]["payload"] == {"nested": {"x": 1, "y": [1, 2, 3]}}
    assert data["event"]["group_id"] == "grp-1"
    assert "first_failed_at" in data and "next_retry_at" in data


@pytest.mark.asyncio
async def test_reload_from_disk_recovers_entries(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path)
    await dlq.add(_event("t1"), "err")
    await dlq.add(_event("t2"), "err")

    revived = _dlq(tmp_path)
    assert await revived.size() == 2
    assert "t1" in revived._entries
    assert "t2" in revived._entries
    assert revived._entries["t1"].in_flight is False


@pytest.mark.asyncio
async def test_add_increments_attempts_for_existing_entry(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path)
    e1 = await dlq.add(_event("t1"), "err 1")
    e2 = await dlq.add(_event("t1"), "err 2")
    assert e1 is not None and e1.attempts == 0
    assert e2 is not None and e2.attempts == 1
    assert e2.first_failed_at == e1.first_failed_at
    assert e2.last_error == "err 2"


@pytest.mark.asyncio
async def test_max_entries_evicts_oldest_when_cap_exceeded(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, max_entries=3)
    for i in range(3):
        await dlq.add(_event(f"t{i}"), "err")
    assert await dlq.size() == 3
    await dlq.add(_event("t-new"), "err")
    assert await dlq.size() == 3
    assert "t0" not in dlq._entries
    assert "t-new" in dlq._entries
    assert not (Path(tmp_path) / "hook" / "t0.json").exists()


@pytest.mark.asyncio
async def test_eviction_picks_oldest_first_failed_at(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, max_entries=2)
    e0 = await dlq.add(_event("t0"), "err")
    e1 = await dlq.add(_event("t1"), "err")
    assert e0 is not None and e1 is not None
    e0.first_failed_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    await dlq.add(_event("t2"), "err")
    assert "t0" not in dlq._entries
    assert "t1" in dlq._entries and "t2" in dlq._entries


@pytest.mark.asyncio
async def test_eviction_skips_in_flight_allowing_overshoot(tmp_path: Path) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.01, max_entries=1)
    await dlq.add(_event("t-flying"), "err")
    await asyncio.sleep(0.02)
    flying = await dlq.try_pop_ready()
    assert flying is not None and flying.in_flight is True
    await dlq.add(_event("t-new"), "err")
    assert "t-flying" in dlq._entries
    assert "t-new" in dlq._entries
    assert await dlq.size() == 2


@pytest.mark.asyncio
async def test_max_backoff_caps_delay(tmp_path: Path) -> None:
    dlq = _dlq(
        tmp_path,
        initial_backoff_seconds=1.0,
        max_backoff_seconds=2.0,
        backoff_multiplier=10.0,
        max_age_seconds=1000.0,
    )
    e1 = await dlq.add(_event("t1"), "e")
    assert e1 is not None
    e2 = await dlq.add(_event("t1"), "e")
    assert e2 is not None
    e3 = await dlq.add(_event("t1"), "e")
    assert e3 is not None
    now = datetime.now(timezone.utc)
    assert (e3.next_retry_at - now).total_seconds() <= 2.0 + 0.5


class _DLQProcessor(AbstractWebhookProcessor):
    raised: Exception | None = None

    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        if self.raised is not None:
            raise self.raised
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["repository"]


@pytest.fixture
async def manager() -> Any:
    mgr = LiveEventsProcessorManager(APIRouter(), SignalHandler(), 3.0, 3.0)
    yield mgr
    pending = list(mgr._pending_get_tasks.values())
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def test_should_dead_letter_default() -> None:
    proc = _DLQProcessor(_event())
    assert proc.should_dead_letter(RateLimitError("rate limit")) is True
    assert proc.should_dead_letter(DeadLetterableError("custom")) is True
    assert proc.should_dead_letter(ValueError("boom")) is False


@pytest.mark.asyncio
async def test_dlq_disabled_returns_no_settings(
    manager: LiveEventsProcessorManager,
) -> None:
    mock_config = MagicMock()
    mock_config.webhook_dlq = WebhookDeadLetterQueueSettings(enabled=False)
    with patch(
        "port_ocean.core.handlers.webhook.processor_manager.ocean"
    ) as ocean_mock:
        ocean_mock.integration.context.config = mock_config
        assert manager._dlq_settings() is None
        assert manager._ensure_dlq("/p") is None


@pytest.mark.asyncio
async def test_dlq_enabled_returns_settings(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    mock_config = MagicMock()
    mock_config.webhook_dlq = WebhookDeadLetterQueueSettings(
        enabled=True,
        storage_path=str(tmp_path),
        max_age_seconds=10,
        initial_backoff_seconds=0.01,
        max_backoff_seconds=1.0,
        backoff_multiplier=2.0,
    )
    with patch(
        "port_ocean.core.handlers.webhook.processor_manager.ocean"
    ) as ocean_mock:
        ocean_mock.integration.context.config = mock_config
        settings = manager._dlq_settings()
        assert settings is not None and settings.enabled is True
        dlq = manager._ensure_dlq("/p")
        assert dlq is not None
        assert manager._ensure_dlq("/p") is dlq


@pytest.mark.asyncio
async def test_handle_dlq_outcome_adds_eligible_failure(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    dlq = _dlq(tmp_path)
    manager._dlqs["/p"] = dlq
    await manager._handle_dlq_outcome(
        path="/p",
        event=_event("t1"),
        dlq_entry=None,
        dlq_eligible_error=RateLimitError("boom"),
        any_failure=True,
    )
    assert await dlq.size() == 1


@pytest.mark.asyncio
async def test_handle_dlq_outcome_ignores_non_eligible_failure(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    dlq = _dlq(tmp_path)
    manager._dlqs["/p"] = dlq
    await manager._handle_dlq_outcome(
        path="/p",
        event=_event("t1"),
        dlq_entry=None,
        dlq_eligible_error=None,
        any_failure=True,
    )
    assert await dlq.size() == 0


@pytest.mark.asyncio
async def test_handle_dlq_outcome_replay_success_clears_entry(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.01)
    manager._dlqs["/p"] = dlq
    await dlq.add(_event("t1"), "err")
    await asyncio.sleep(0.02)
    entry = await dlq.try_pop_ready()
    assert entry is not None
    await manager._handle_dlq_outcome(
        path="/p",
        event=_event("t1"),
        dlq_entry=entry,
        dlq_eligible_error=None,
        any_failure=False,
    )
    assert await dlq.size() == 0


@pytest.mark.asyncio
async def test_handle_dlq_outcome_replay_failure_re_queues(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.01)
    manager._dlqs["/p"] = dlq
    await dlq.add(_event("t1"), "err")
    await asyncio.sleep(0.02)
    entry = await dlq.try_pop_ready()
    assert entry is not None and entry.attempts == 0
    await manager._handle_dlq_outcome(
        path="/p",
        event=_event("t1"),
        dlq_entry=entry,
        dlq_eligible_error=RateLimitError("again"),
        any_failure=True,
    )
    assert "t1" in dlq._entries
    assert dlq._entries["t1"].attempts == 1


@pytest.mark.asyncio
async def test_handle_dlq_outcome_swallows_internal_errors(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    dlq = _dlq(tmp_path)
    dlq.add = AsyncMock(side_effect=OSError("disk full"))  # type: ignore[method-assign]
    manager._dlqs["/p"] = dlq
    await manager._handle_dlq_outcome(
        path="/p",
        event=_event("t1"),
        dlq_entry=None,
        dlq_eligible_error=RateLimitError("boom"),
        any_failure=True,
    )


@pytest.mark.asyncio
async def test_next_event_prefers_ready_dlq_over_main_queue(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    path = "/hook"
    manager.register_processor(path, _DLQProcessor)
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.005)
    manager._dlqs[path] = dlq
    await manager._event_queues[path].put(_event("from-main"))
    await dlq.add(_event("from-dlq"), "err")
    await asyncio.sleep(0.02)

    event, entry = await manager._next_event(path, worker_id=0)
    assert entry is not None
    assert event.trace_id == "from-dlq"

    event, entry = await manager._next_event(path, worker_id=0)
    assert entry is None
    assert event.trace_id == "from-main"


@pytest.mark.asyncio
async def test_next_event_falls_back_to_main_when_dlq_empty(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    path = "/hook"
    manager.register_processor(path, _DLQProcessor)
    manager._dlqs[path] = _dlq(tmp_path)
    await manager._event_queues[path].put(_event("only"))
    event, entry = await manager._next_event(path, worker_id=0)
    assert entry is None
    assert event.trace_id == "only"


@pytest.mark.asyncio
async def test_next_event_waits_for_dlq_to_become_ready(
    manager: LiveEventsProcessorManager, tmp_path: Path
) -> None:
    path = "/hook"
    manager.register_processor(path, _DLQProcessor)
    dlq = _dlq(tmp_path, initial_backoff_seconds=0.05)
    manager._dlqs[path] = dlq
    await dlq.add(_event("delayed"), "err")
    event, entry = await asyncio.wait_for(
        manager._next_event(path, worker_id=0), timeout=2.0
    )
    assert entry is not None
    assert event.trace_id == "delayed"
