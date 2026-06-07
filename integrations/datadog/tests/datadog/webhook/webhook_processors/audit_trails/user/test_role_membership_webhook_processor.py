from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor import (
    RoleMembershipWebhookProcessor,
)


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
def processor() -> RoleMembershipWebhookProcessor:
    return RoleMembershipWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.mark.asyncio
async def test_should_process_event_role_membership_change(
    processor: RoleMembershipWebhookProcessor,
) -> None:
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
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": "modified",
            "asset": {"type": "role", "id": "role-1"},
        }
    }
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_role_membership_refetches_user(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "user-uuid-1"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event("modified", "role-1", "user-uuid-1"),
            resource_config={},  # type: ignore[arg-type]
        )

    exporter.get_resource.assert_awaited_once_with("user-uuid-1")
    assert result.updated_raw_results == [{"id": "user-uuid-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_role_event_never_deletes_user(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """Even if the role itself were deleted, we never delete the user record."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "user-uuid-1"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event("deleted", "role-1", "user-uuid-1"),
            resource_config={},  # type: ignore[arg-type]
        )

    assert result.deleted_raw_results == []
    assert result.updated_raw_results == [{"id": "user-uuid-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: RoleMembershipWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
