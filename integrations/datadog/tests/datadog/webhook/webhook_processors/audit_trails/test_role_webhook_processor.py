from typing import Any

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
async def test_get_matching_kinds(processor: RoleWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.ROLE]


@pytest.mark.asyncio
async def test_validate_payload_always_true(processor: RoleWebhookProcessor) -> None:
    assert await processor.validate_payload(_event("modified", "r-1")) is True
    assert await processor.validate_payload({"whatever": "dict"}) is True
