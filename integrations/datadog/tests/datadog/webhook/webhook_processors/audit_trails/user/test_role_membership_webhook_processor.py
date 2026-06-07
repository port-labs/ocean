from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor import (
    RoleMembershipWebhookProcessor,
    _extract_target_user_email,
)

_ROLE_MEMBERSHIP_PATH = "/api/v2/roles/role-uuid/users"


def _role_membership_event(
    action: str = "modified",
    role_id: str = "role-1",
    actor_email: str = "admin@corp.io",
    target_email: str = "bob@corp.io",
    url_path: str = _ROLE_MEMBERSHIP_PATH,
    include_http: bool = True,
) -> dict[str, Any]:
    """Simulate an Access Management audit event for a role-membership change.

    Datadog emits this when a user is added to or removed from a role:
    - asset.type  == "user"  (the affected user, not the role)
    - action      == "modified"
    - http.url_details.path starts with "/api/v2/roles"
    - msg         contains 'added/removed user "<email>"'
    """
    verb = "added" if "added" in url_path or action != "modified" else "removed"
    msg = f'{actor_email} successfully {verb} user "{target_email}" from the role "Datadog Read Only Role"'
    attrs: dict[str, Any] = {
        "evt": {"name": "Access Management"},
        "action": action,
        "asset": {"type": "user", "id": target_email},
        "msg": msg,
    }
    if include_http:
        attrs["http"] = {
            "method": "PATCH",
            "status_code": 200,
            "url_details": {"path": url_path},
        }
    return {"attributes": attrs}


@pytest.fixture
def processor() -> RoleMembershipWebhookProcessor:
    return RoleMembershipWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


# ---------------------------------------------------------------------------
# _extract_target_user_email unit tests
# ---------------------------------------------------------------------------


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
        # verb must be "added" or "removed" — other prefixes don't match
        ('mentioned user "bob@corp.io" in a comment', None),
        # quoted value must contain "@" — display names don't match
        ('removed user "Bob Smith" from the role "Admin"', None),
        ("no user email here", None),
        (None, None),
    ],
)
def test_extract_target_user_email(msg: str | None, expected: str | None) -> None:
    assert _extract_target_user_email(msg) == expected


# ---------------------------------------------------------------------------
# _should_process tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_process_event_matches_role_membership(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="ok",
                payload=_role_membership_event(),
                headers={},
            )
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_action(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """Only 'modified' action triggers a membership change event."""
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_role_membership_event(action="deleted"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = _role_membership_event()
    event["attributes"]["asset"]["type"] = "role"
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = _role_membership_event()
    event["attributes"]["evt"]["name"] = "Monitor"
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_no_http(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """Without the http field we cannot confirm this is a roles API call."""
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_role_membership_event(include_http=False),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_non_roles_url(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """An Access Management event against a non-roles URL is not a membership change."""
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_role_membership_event(url_path="/api/v2/users/some-id"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_no_msg(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = _role_membership_event()
    del event["attributes"]["msg"]
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_msg_without_email(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    event = _role_membership_event()
    event["attributes"]["msg"] = "some unrelated message"
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=event, headers={})
        )
        is False
    )


# ---------------------------------------------------------------------------
# _handle_audit_event tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_event_fetches_user_by_email(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource_by_email.return_value = {
            "id": "uuid-bob",
            "attributes": {"email": "bob@corp.io"},
        }
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event(),
            resource_config={},  # type: ignore[arg-type]
        )

    exporter.get_resource_by_email.assert_awaited_once_with("bob@corp.io")
    assert result.updated_raw_results == [
        {"id": "uuid-bob", "attributes": {"email": "bob@corp.io"}}
    ]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_user_not_found_returns_empty(
    processor: RoleMembershipWebhookProcessor,
) -> None:
    """When Datadog returns no user for the email, emit nothing."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.user.role_membership_webhook_processor.UserExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource_by_email.return_value = None
        cls.return_value = exporter

        result = await processor.handle_event(
            _role_membership_event(),
            resource_config={},  # type: ignore[arg-type]
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


# ---------------------------------------------------------------------------
# get_matching_kinds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: RoleMembershipWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.USER]
