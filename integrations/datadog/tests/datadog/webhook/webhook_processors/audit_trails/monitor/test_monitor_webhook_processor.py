from types import SimpleNamespace
from typing import Any

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.monitor.monitor_webhook_processor import (
    MonitorWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "monitor",
    evt_name: str = "Monitor",
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


@pytest.fixture
def processor() -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_monitor_type(
    processor: MonitorWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event("modified", "m-1"), headers={})
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: MonitorWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no", payload=_event("modified", "u-1", "user"), headers={}
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: MonitorWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("modified", "m-1", evt_name="Access Management"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_resolved_action(
    processor: MonitorWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=_event("resolved", "m-1"), headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_delete_returns_deleted(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(_event("deleted", "m-1"), resource_config)  # type: ignore[arg-type]
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {"type": "monitor", "id": "m-1", "name": None}
    ]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: MonitorWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.MONITOR]
