import pytest
from unittest.mock import AsyncMock, MagicMock

from github.webhook.webhook_processors.organization_webhook_processor import (
    OrganizationWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestOrganizationWebhookProcessor:
    """Test the organization webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "organization"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> OrganizationWebhookProcessor:
        """Create an OrganizationWebhookProcessor instance"""
        return OrganizationWebhookProcessor(event=mock_event)

    async def test_get_matching_kinds_repository(self, processor: OrganizationWebhookProcessor) -> None:
        """Test get_matching_kinds for repository event"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "repository"},
            payload={},
        )
        assert await processor.get_matching_kinds(event) == [ObjectKind.REPOSITORY]

    async def test_get_matching_kinds_member(self, processor: OrganizationWebhookProcessor) -> None:
        """Test get_matching_kinds for member event"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "member"},
            payload={},
        )
        assert await processor.get_matching_kinds(event) == [ObjectKind.USER]

    async def test_get_matching_kinds_team(self, processor: OrganizationWebhookProcessor) -> None:
        """Test get_matching_kinds for team event"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "team"},
            payload={},
        )
        assert await processor.get_matching_kinds(event) == [ObjectKind.TEAM]

    async def test_handle_repository_created(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling repository created event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "created",
            "event_type": "repository",
            "organization": {"id": 1, "login": "test-org"},
            "repository": {
                "id": 123,
                "full_name": "test-org/test-repo",
                "name": "test-repo",
            },
        }

        expected_repo = {
            "id": 123,
            "full_name": "test-org/test-repo",
            "name": "test-repo",
            "owner": {"login": "test-org"},
        }

        mock_response = MagicMock()
        mock_response.json.return_value = expected_repo

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_repository = AsyncMock(return_value=mock_response)

        result = await processor.handle_event(payload, resource_config)

        processor._github_webhook_client.get_repository.assert_called_once_with("test-org/test-repo")
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_repo
        assert not result.deleted_raw_results

    async def test_handle_repository_deleted(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling repository deleted event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "deleted",
            "event_type": "repository",
            "organization": {"id": 1, "login": "test-org"},
            "repository": {
                "id": 123,
                "full_name": "test-org/test-repo",
                "name": "test-repo",
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["repository"]

    async def test_handle_member_added(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling member added event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "added",
            "event_type": "member",
            "organization": {"id": 1, "login": "test-org"},
            "member": {
                "id": 456,
                "login": "testuser",
                "type": "User",
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == payload["member"]
        assert result.updated_raw_results[0]["organization"] == payload["organization"]
        assert not result.deleted_raw_results

    async def test_handle_member_removed(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling member removed event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "removed",
            "event_type": "member",
            "organization": {"id": 1, "login": "test-org"},
            "member": {
                "id": 456,
                "login": "testuser",
                "type": "User",
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["member"]

    async def test_handle_team_created(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling team created event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "created",
            "event_type": "team",
            "organization": {"id": 1, "login": "test-org"},
            "team": {
                "id": 789,
                "slug": "test-team",
                "name": "Test Team",
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == payload["team"]
        assert not result.deleted_raw_results

    async def test_handle_team_deleted(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling team deleted event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "deleted",
            "event_type": "team",
            "organization": {"id": 1, "login": "test-org"},
            "team": {
                "id": 789,
                "slug": "test-team",
                "name": "Test Team",
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["team"]

    async def test_handle_unhandled_event(self, processor: OrganizationWebhookProcessor) -> None:
        """Test handling unhandled organization event"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "renamed",
            "event_type": "organization",
            "organization": {"id": 1, "login": "test-org"},
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_validate_payload_valid(self, processor: OrganizationWebhookProcessor) -> None:
        """Test validate_payload with valid payloads"""

        assert await processor.validate_payload({"organization": {"id": 1}}) is True

        assert await processor.validate_payload({"repository": {"id": 123}}) is True

        assert await processor.validate_payload({"member": {"id": 456}}) is True

        assert await processor.validate_payload({"team": {"id": 789}}) is True

    async def test_validate_payload_invalid(self, processor: OrganizationWebhookProcessor) -> None:
        """Test validate_payload with invalid payload"""
        assert await processor.validate_payload({}) is False
        assert await processor.validate_payload({"other": "data"}) is False
