import pytest
from unittest.mock import AsyncMock, patch
from github.webhook.webhook_processors.collaborator_webhook_processor import (
    CollaboratorWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.mark.asyncio
class TestCollaboratorWebhookProcessor:
    async def test_should_process_event_valid_member_added(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"action": "added", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_valid_member_edited(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"action": "edited", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_valid_member_removed(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"action": "removed", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_valid_membership_added(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "membership"},
            payload={
                "action": "added", 
                "organization": {"login": "test-org"}, 
                "team": {"name": "test-team"}, 
                "member": {"login": "test-user"}
            },
        )

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_valid_team_added_to_repository(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "team"},
            payload={
                "action": "added_to_repository", 
                "organization": {"login": "test-org"}, 
                "team": {"name": "test-team"},
                "repository": {"name": "test-repo"}
            },
        )

        result = await processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_invalid_event_type(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "repository"},
            payload={"action": "added", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is False

    async def test_should_process_event_invalid_action(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"action": "deleted", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is False

    async def test_should_process_event_no_action(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        result = await processor._should_process_event(event)
        assert result is False

    async def test_get_matching_kinds(self) -> None:
        processor = CollaboratorWebhookProcessor()
        event = WebhookEvent(
            headers={"x-github-event": "member"},
            payload={"action": "added", "repository": {"name": "test-repo"}, "member": {"login": "test-user"}},
        )

        kinds = await processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.COLLABORATOR]

    async def test_validate_payload_member_valid(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "member",
            "action": "added",
            "repository": {"name": "test-repo"},
            "member": {"login": "test-user"},
        }

        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_membership_valid(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "membership",
            "action": "added",
            "organization": {"login": "test-org"},
            "team": {"name": "test-team"},
            "member": {"login": "test-user"},
        }

        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_team_valid(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "team",
            "action": "added_to_repository",
            "organization": {"login": "test-org"},
            "team": {"name": "test-team"},
        }

        result = await processor.validate_payload(payload)
        assert result is True

    async def test_validate_payload_member_missing_fields(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "member",
            "action": "added",
            "repository": {"name": "test-repo"},
            # Missing member field
        }

        result = await processor.validate_payload(payload)
        assert result is False

    async def test_validate_payload_member_missing_repository_name(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "member",
            "action": "added",
            "repository": {},  # Missing name
            "member": {"login": "test-user"},
        }

        result = await processor.validate_payload(payload)
        assert result is False

    async def test_validate_payload_member_missing_member_login(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "member",
            "action": "added",
            "repository": {"name": "test-repo"},
            "member": {},  # Missing login
        }

        result = await processor.validate_payload(payload)
        assert result is False

    async def test_validate_payload_unknown_event_type(self) -> None:
        processor = CollaboratorWebhookProcessor()
        payload = {
            "__event_name": "unknown",
            "action": "added",
        }

        result = await processor.validate_payload(payload)
        assert result is False 