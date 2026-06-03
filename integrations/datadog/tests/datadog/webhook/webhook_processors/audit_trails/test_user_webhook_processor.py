from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user_webhook_processor import (
    UserWebhookProcessor,
)


@pytest.fixture
def processor() -> UserWebhookProcessor:
    return UserWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.mark.asyncio
async def test_should_process_event_matches_user_type(
    processor: UserWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="ok",
        payload={"event": {"action": "resource.update", "asset": {"type": "user"}}},
        headers={},
    )
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_handle_event_with_delete_action_returns_deleted(
    processor: UserWebhookProcessor,
) -> None:
    result = await processor.handle_event(
        {"event": {"action": "resource.remove", "asset": {"id": "u-1"}}},
        resource_config={},
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "u-1"}]


@pytest.mark.asyncio
async def test_handle_event_converts_404_to_deleted(
    processor: UserWebhookProcessor,
) -> None:
    error_response = httpx.Response(
        404, request=httpx.Request("GET", "https://api.datadoghq.com/api/v2/users/u-1")
    )
    not_found = httpx.HTTPStatusError(
        "not found",
        request=error_response.request,
        response=error_response,
    )
    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.user_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.user_webhook_processor.UserExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "u-1"}}},
            resource_config={},
        )

    exporter.get_resource.assert_awaited_once_with("u-1")
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "u-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds_and_validate_payload(
    processor: UserWebhookProcessor,
) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
    assert await processor.validate_payload({"event": {"asset": {"id": "u-1"}}}) is True
    assert await processor.validate_payload({"event": {"asset": {}}}) is False
