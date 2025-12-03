import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    """Test the issue webhook processor"""

    @pytest.fixture
    def issue_payload(self) -> dict[str, Any]:
        """Create a sample issue webhook payload"""
        return {
            "object_kind": "issue",
            "event_type": "issue",
            "user": {"name": "Test User", "username": "testuser"},
            "project": {"id": 123, "name": "Test Project"},
            "object_attributes": {
                "id": 456,
                "iid": 1,
                "state": "opened",
                "type": "issue",
                "labels": [],
                "updated_at": "2025-12-02 21:00:00 UTC",
            },
        }

    @pytest.fixture
    def mock_event(self, issue_payload: dict[str, Any]) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "issue"},
            payload=issue_payload,
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> IssueWebhookProcessor:
        """Create an IssueWebhookProcessor instance"""
        return IssueWebhookProcessor(event=mock_event)

    @pytest.fixture
    def resource_config(self) -> MagicMock:
        """Create a mock resource config with selector"""
        config = MagicMock()
        config.selector = MagicMock()
        config.selector.state = None
        config.selector.issue_type = None
        config.selector.labels = None
        config.selector.updated_after = None
        return config

    async def test_get_matching_kinds(
        self, processor: IssueWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the ISSUE kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.ISSUE]

    async def test_handle_event(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event with no selectors"""
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {
            "id": issue_id,
            "object_kind": "issue",
            "event_type": "issue",
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_issue
        assert not result.deleted_raw_results

    async def test_handle_event_state_selector_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when state selector matches"""
        resource_config.selector.state = "opened"
        issue_payload["object_attributes"]["state"] = "opened"
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_issue

    async def test_handle_event_state_selector_no_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when state selector does not match"""
        resource_config.selector.state = "closed"
        issue_payload["object_attributes"]["state"] = "opened"
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_issue_type_selector_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when issue_type selector matches"""
        resource_config.selector.issue_type = "incident"
        issue_payload["object_attributes"]["type"] = "incident"
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_issue_type_selector_no_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when issue_type selector does not match"""
        resource_config.selector.issue_type = "incident"
        issue_payload["object_attributes"]["type"] = "issue"
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_issue_type_case_insensitive(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test that issue_type selector handles case differences"""
        resource_config.selector.issue_type = "task"
        issue_payload["object_attributes"]["type"] = "TASK"
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once()
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_labels_selector_match_single(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when labels selector matches (single label)"""
        resource_config.selector.labels = "bug"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "bug"},
            {"title": "high-priority"},
        ]
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_labels_selector_match_multiple(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when labels selector matches (multiple labels)"""
        resource_config.selector.labels = "bug, high-priority"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "bug"},
            {"title": "high-priority"},
            {"title": "backend"},
        ]
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_labels_selector_partial_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when labels selector has partial match (should not process)"""
        resource_config.selector.labels = "bug, critical, security"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "bug"},
            {"title": "high-priority"},
        ]
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_labels_selector_no_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when labels selector does not match"""
        resource_config.selector.labels = "bug"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "feature"},
            {"title": "enhancement"},
        ]
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_labels_selector_empty_labels(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when labels selector is set but issue has no labels"""
        resource_config.selector.labels = "bug"
        issue_payload["object_attributes"]["labels"] = []
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0

    async def test_handle_event_updated_after_selector_recent_issue(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling a recently updated issue with updated_after selector"""
        from datetime import datetime, timedelta, timezone

        resource_config.selector.updated_after = 7  # 7 days
        # Create a date within the last 7 days
        recent_date = datetime.now(timezone.utc) - timedelta(days=3)
        resource_config.selector.updated_after_datetime = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()
        issue_payload["object_attributes"]["updated_at"] = recent_date.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_multiple_selectors_all_match(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when multiple selectors all match"""
        resource_config.selector.state = "opened"
        resource_config.selector.issue_type = "bug"
        resource_config.selector.labels = "urgent, backend"
        resource_config.selector.updated_after = 7
        resource_config.selector.updated_after_datetime = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()

        recent_date = datetime.now(timezone.utc) - timedelta(days=2)
        issue_payload["object_attributes"]["state"] = "opened"
        issue_payload["object_attributes"]["type"] = "bug"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "urgent"},
            {"title": "backend"},
            {"title": "critical"},
        ]
        issue_payload["object_attributes"]["updated_at"] = recent_date.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_multiple_selectors_one_fails(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test handling an issue event when one selector fails (should not process)"""

        resource_config.selector.state = "opened"
        resource_config.selector.issue_type = "bug"
        resource_config.selector.labels = "urgent, backend"

        issue_payload["object_attributes"]["state"] = "closed"  # This doesn't match
        issue_payload["object_attributes"]["type"] = "bug"
        issue_payload["object_attributes"]["labels"] = [
            {"title": "urgent"},
            {"title": "backend"},
        ]

        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        # Should not call API because state selector failed
        processor._gitlab_webhook_client.get_issue.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_labels_with_whitespace(
        self,
        processor: IssueWebhookProcessor,
        issue_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Test that labels selector handles whitespace correctly"""
        resource_config.selector.labels = "  bug  ,  high-priority  "
        issue_payload["object_attributes"]["labels"] = [
            {"title": "bug"},
            {"title": "high-priority"},
        ]
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {"id": issue_id}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1
