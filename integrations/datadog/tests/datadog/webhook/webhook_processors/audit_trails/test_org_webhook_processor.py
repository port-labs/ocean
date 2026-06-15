from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.org_webhook_processor import (
    OrgWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "organization",
    evt_name: str = "Organization Management",
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


@pytest.fixture
def processor() -> OrgWebhookProcessor:
    return OrgWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.mark.asyncio
async def test_should_process_event_matches_org_type(
    processor: OrgWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event("created", "o-1"), headers={})
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: OrgWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no", payload=_event("created", "r-1", "role"), headers={}
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: OrgWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("created", "o-1", evt_name="Access Management"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_unsupported_action(
    processor: OrgWebhookProcessor,
) -> None:
    # Only "created" is tracked for the organization asset type.
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=_event("modified", "o-1"), headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: OrgWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.ORG]


@pytest.mark.asyncio
async def test_validate_payload_always_true(processor: OrgWebhookProcessor) -> None:
    assert await processor.validate_payload(_event("created", "o-1")) is True
    assert await processor.validate_payload({"whatever": "dict"}) is True


@pytest.mark.asyncio
async def test_handle_event_fetches_org(processor: OrgWebhookProcessor) -> None:
    org = {"public_id": "o-1", "name": "Org One"}
    payload = _event("created", "o-1")

    with patch(
        "datadog.webhook.webhook_processors.audit_trails.org_webhook_processor.OrgExporter"
    ) as mock_exporter_cls:
        mock_exporter = mock_exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=org)

        results = await processor.handle_event(payload, resource_config=None)  # type: ignore[arg-type]

        assert results.updated_raw_results == [org]
        assert results.deleted_raw_results == []
        # The fetched id comes from the event's asset id.
        assert mock_exporter.get_resource.call_args.args[0].resource_id == "o-1"
