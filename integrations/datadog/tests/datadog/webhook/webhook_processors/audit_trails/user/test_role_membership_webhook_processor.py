from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor import (
    RoleMembershipWebhookProcessor,
    _extract_target_user_email,
)


def _role_membership_event(
    action: str,
    role_id: str,
    actor_email: str,
    target_email: str,
) -> dict[str, Any]:
    """User added/removed from a role — asset is the role, msg carries target email."""
    msg = (
        f'{actor_email} successfully {"added" if action != "deleted" else "removed"} '
        f'user "{target_email}" from the role "Datadog Read Only Role"'
    )
    return {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": action,
            "asset": {"type": "role", "id": role_id},
            "msg": msg,
        }
    }


@pytest.fixture
def processor() -> RoleMembershipWebhookProcessor:
    return RoleMembershipWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.mark.parametrize(
    "msg,expected",
    [
        (
            'admin@corp.io successfully added user "bob@corp.io" from the role "Read Only"',
            "bob@corp.io",
        ),
        (
            'admin@corp.io successfully removed user "alice@corp.io" from the role "Admin"',
            "alice@corp.io",
        ),
        # must not match when there is no action verb before "user"
        ('mentioned user "bob@corp.io" in a comment', None),
        # must not match when the quoted value is not an email
        ('removed user "Bob Smith" from the role "Admin"', None),
        ("no user email here", None),
        (None, None),
    ],
)
def test_extract_target_user_email(msg: str | None, expected: str | None) -> None:
    assert _extract_target_user_email(msg) == expected


@pytest.mark.asyncio
async def test_should_process_event_role_membership_change(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="ok",
                payload=_role_membership_event(
                    "modified", "role-1", "admin@corp.io", "bob@corp.io"
                ),
                headers={},
            )
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_no_msg_skipped(
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
async def test_should_process_event_msg_without_user_skipped(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = {
        "attributes": {
            "evt": {"name": "Access Management"},
            "action": "modified",
            "asset": {"type": "role", "id": "role-1"},
            "msg": "some unrelated message",
        }
    }
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_refetches_user_by_email(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource_by_email.return_value = {
            "id": "uuid-bob",
            "email": "bob@corp.io",
        }
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event(
                "modified", "role-1", "admin@corp.io", "bob@corp.io"
            ),
            resource_config={},  # type: ignore[arg-type]
        )

    exporter.get_resource_by_email.assert_awaited_once_with("bob@corp.io")
    assert result.updated_raw_results == [{"id": "uuid-bob", "email": "bob@corp.io"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_role_event_never_deletes_user(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """Even when the action is 'deleted', we re-fetch the user rather than delete them."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource_by_email.return_value = {"id": "uuid-bob"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event("deleted", "role-1", "admin@corp.io", "bob@corp.io"),
            resource_config={},  # type: ignore[arg-type]
        )

    assert result.deleted_raw_results == []
    assert result.updated_raw_results == [{"id": "uuid-bob"}]


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: RoleMembershipWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
