from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.role_webhook_processor import (
    RoleWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "role",
    evt_name: str = "Access Management",
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


@pytest.fixture
def processor() -> RoleWebhookProcessor:
    return RoleWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.mark.asyncio
async def test_should_process_event_matches_role_type(
    processor: RoleWebhookProcessor,
) -> None:
    # correct evt.name + asset.type → True
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event("modified", "r-1"), headers={})
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: RoleWebhookProcessor,
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
    processor: RoleWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("modified", "r-1", evt_name="Monitor"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_unsupported_action(
    processor: RoleWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=_event("accessed", "r-1"), headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_delete_returns_deleted(
    processor: RoleWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        _event("deleted", "r-1"), resource_config={}  # type: ignore[arg-type]
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "r-1"}]


@pytest.mark.asyncio
async def test_handle_single_event_404_returns_deleted(
    processor: RoleWebhookProcessor,
) -> None:
    req = httpx.Request("GET", "https://api.datadoghq.com/api/v2/role/r-1")
    not_found = httpx.HTTPStatusError(
        "not found", request=req, response=httpx.Response(404, request=req)
    )
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.role_webhook_processor.RoleExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "r-1"), resource_config={}  # type: ignore[arg-type]
        )

    exporter.get_resource.assert_awaited_once_with("r-1")
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "r-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: RoleWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.ROLE]


@pytest.mark.asyncio
async def test_validate_payload_always_true(processor: RoleWebhookProcessor) -> None:
    assert await processor.validate_payload(_event("modified", "r-1")) is True
    assert await processor.validate_payload({"whatever": "dict"}) is True
