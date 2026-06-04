import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

overrides_module = sys.modules.setdefault("overrides", types.ModuleType("overrides"))
setattr(overrides_module, "SLOResourceConfig", object)
setattr(overrides_module, "TeamResourceConfig", object)

from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor import (
    SloWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "slo",
    evt_name: str = "SLO",
) -> dict:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


@pytest.fixture
def processor() -> SloWebhookProcessor:
    return SloWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_slo_type(processor: SloWebhookProcessor) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="ok", payload=_event("modified", "s-1"), headers={})
    ) is True


@pytest.mark.asyncio
async def test_should_process_event_accepts_any_action(processor: SloWebhookProcessor) -> None:
    for action in ("created", "modified", "deleted"):
        assert await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event(action, "s-1"), headers={})
        ) is True


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(processor: SloWebhookProcessor) -> None:
    assert await processor.should_process_event(
        WebhookEvent(
            trace_id="no",
            payload=_event("modified", "s-1", evt_name="Monitor"),
            headers={},
        )
    ) is False


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(processor: SloWebhookProcessor) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="no", payload=_event("modified", "m-1", "monitor"), headers={})
    ) is False


@pytest.mark.asyncio
async def test_handle_single_event_delete_returns_deleted(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(
        _event("deleted", "s-1"), resource_config=resource_config
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "s-1"}]


@pytest.mark.asyncio
async def test_handle_single_event_fetches_slo_with_restriction_policy_flag(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.SloExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "s-1"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "s-1"), resource_config=resource_config
        )

    exporter.get_resource.assert_awaited_once_with(
        GetSloOptions(id="s-1", include_restriction_policy=True)
    )
    assert result.updated_raw_results == [{"id": "s-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_404_returns_deleted(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    req = httpx.Request("GET", "https://api.datadoghq.com/api/v1/slo/s-1")
    not_found = httpx.HTTPStatusError(
        "not found", request=req, response=httpx.Response(404, request=req)
    )
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.SloExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "s-1"), resource_config=resource_config
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "s-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: SloWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.SLO]
