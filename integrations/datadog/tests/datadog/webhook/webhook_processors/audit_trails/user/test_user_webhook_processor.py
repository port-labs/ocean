from typing import Any

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user.user_webhook_processor import (
    UserWebhookProcessor,
)


_USER_HTTP = {
    "method": "PATCH",
    "status_code": 200,
    "url_details": {"path": "/api/v2/users/u-1"},
}


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "user",
    evt_name: str = "Access Management",
    include_http: bool = True,
) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "evt": {"name": evt_name},
        "action": action,
        "asset": {"type": asset_type, "id": asset_id},
    }
    if include_http:
        attrs["http"] = _USER_HTTP
    return {"attributes": attrs}


@pytest.fixture
def processor() -> UserWebhookProcessor:
    return UserWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.mark.asyncio
async def test_should_process_event_matches_user_type(
    processor: UserWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event("modified", "u-1"), headers={})
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: UserWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no", payload=_event("modified", "r-1", "role"), headers={}
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_no_http(
    processor: UserWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("modified", "u-1", include_http=False),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: UserWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("modified", "u-1", evt_name="Monitor"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_delete_returns_deleted(
    processor: UserWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        _event("deleted", "u-1"), resource_config={}  # type: ignore[arg-type]
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"type": "user", "id": "u-1", "name": None}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: UserWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
