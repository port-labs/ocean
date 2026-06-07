from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user_webhook_processor import (
    UserWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "user",
    evt_name: str = "Access Management",
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


def _role_membership_event(action: str, role_id: str, user_uuid: str) -> dict[str, Any]:
    """User added/removed from a role — asset is the role, usr is the affected user."""
    return {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": action,
            "asset": {"type": "role", "id": role_id},
            "usr": {"uuid": user_uuid, "id": f"{user_uuid}@example.com"},
        }
    }


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
    assert result.deleted_raw_results == [{"id": "u-1"}]


@pytest.mark.asyncio
async def test_handle_single_event_404_returns_deleted(
    processor: UserWebhookProcessor,
) -> None:
    req = httpx.Request("GET", "https://api.datadoghq.com/api/v2/users/u-1")
    not_found = httpx.HTTPStatusError(
        "not found", request=req, response=httpx.Response(404, request=req)
    )
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "u-1"), resource_config={}  # type: ignore[arg-type]
        )

    exporter.get_resource.assert_awaited_once_with("u-1")
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "u-1"}]


@pytest.mark.asyncio
async def test_should_process_event_role_membership_change(
    processor: UserWebhookProcessor,
) -> None:
    # role:modified with usr field → user was added/removed from a role
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="ok",
                payload=_role_membership_event("modified", "role-1", "user-uuid-1"),
                headers={},
            )
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_role_no_usr_skipped(
    processor: UserWebhookProcessor,
) -> None:
    # role:modified without usr → can't identify the user, skip
    event = _event("modified", "role-1", "role")
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_role_membership_refetches_user(
    processor: UserWebhookProcessor,
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "user-uuid-1"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event("modified", "role-1", "user-uuid-1"),
            resource_config={},  # type: ignore[arg-type]
        )

    # User ID extracted from usr.uuid, never a deletion
    exporter.get_resource.assert_awaited_once_with("user-uuid-1")
    assert result.updated_raw_results == [{"id": "user-uuid-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_role_event_never_deletes_user(
    processor: UserWebhookProcessor,
) -> None:
    """Even if the role itself were deleted, we never delete the user record."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "user-uuid-1"}
        cls.return_value = exporter

        # action=deleted on a role event — should still refetch user, not delete
        result = await processor.handle_event(
            _role_membership_event("deleted", "role-1", "user-uuid-1"),
            resource_config={},  # type: ignore[arg-type]
        )

    assert result.deleted_raw_results == []
    assert result.updated_raw_results == [{"id": "user-uuid-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: UserWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
