from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.webhook_processors.audit_trails.monitor.monitor_restriction_policy_webhook_processor import (
    MonitorRestrictionPolicyWebhookProcessor,
)


def _restriction_policy_event(action: str, resource_id: str) -> dict[str, Any]:
    """Restriction policy event where the embedded resource is a monitor."""
    return {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": action,
            "asset": {"type": "restriction_policy", "id": f"monitor:{resource_id}"},
        }
    }


@pytest.fixture
def processor() -> MonitorRestrictionPolicyWebhookProcessor:
    return MonitorRestrictionPolicyWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_restriction_policy_for_monitor(
    processor: MonitorRestrictionPolicyWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="ok",
                payload=_restriction_policy_event("modified", "m-99"),
                headers={},
            )
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_restriction_policy_non_monitor_skipped(
    processor: MonitorRestrictionPolicyWebhookProcessor,
) -> None:
    event = {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": "modified",
            "asset": {"type": "restriction_policy", "id": "dashboard:d-1"},
        }
    }
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_refetches_monitor(
    processor: MonitorRestrictionPolicyWebhookProcessor,
    resource_config: SimpleNamespace,
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.monitor.monitor_restriction_policy_webhook_processor.MonitorExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "m-99"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _restriction_policy_event("modified", "m-99"), resource_config  # type: ignore[arg-type]
        )

    exporter.get_resource.assert_awaited_once_with(
        GetMonitorOptions(resource_id="m-99", include_restriction_policy=True)
    )
    assert result.updated_raw_results == [{"id": "m-99"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_deleted_restriction_policy_refetches_monitor(
    processor: MonitorRestrictionPolicyWebhookProcessor,
    resource_config: SimpleNamespace,
) -> None:
    """Deleting the restriction policy means the monitor still exists; refetch it."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.monitor.monitor_restriction_policy_webhook_processor.MonitorExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "m-99"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _restriction_policy_event("deleted", "m-99"), resource_config  # type: ignore[arg-type]
        )

    assert result.updated_raw_results == [{"id": "m-99"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: MonitorRestrictionPolicyWebhookProcessor,
) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.MONITOR]
