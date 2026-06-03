import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

# The production module imports these typing aliases from a top-level `overrides` module.
overrides_module = sys.modules.setdefault("overrides", types.ModuleType("overrides"))
setattr(overrides_module, "SLOResourceConfig", object)
setattr(overrides_module, "TeamResourceConfig", object)

from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor import (
    SloWebhookProcessor,
)


@pytest.fixture
def processor() -> SloWebhookProcessor:
    return SloWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_slo_type(
    processor: SloWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="ok",
        payload={"event": {"action": "resource.update", "asset": {"type": "slo"}}},
        headers={},
    )
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_handle_event_with_delete_action_returns_deleted(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(
        {"event": {"action": "resource.remove", "asset": {"id": "s-1"}}},
        resource_config=resource_config,
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "s-1"}]


@pytest.mark.asyncio
async def test_handle_event_fetches_slo_with_restriction_policy_flag(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.SloExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "s-1"}
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "s-1"}}},
            resource_config=resource_config,
        )

    exporter.get_resource.assert_awaited_once_with(
        GetSloOptions(id="s-1", include_restriction_policy=True)
    )
    assert result.updated_raw_results == [{"id": "s-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_converts_404_to_deleted(
    processor: SloWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    error_response = httpx.Response(
        404, request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/slo/s-1")
    )
    not_found = httpx.HTTPStatusError(
        "not found",
        request=error_response.request,
        response=error_response,
    )
    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor.SloExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "s-1"}}},
            resource_config=resource_config,
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "s-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds_and_validate_payload(
    processor: SloWebhookProcessor,
) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.SLO]
    assert await processor.validate_payload({"event": {"asset": {"id": "s-1"}}}) is True
    assert await processor.validate_payload({"event": {"asset": {}}}) is False
