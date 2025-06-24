import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestProjectWebhookProcessor:
    """Test the project webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> ProjectWebhookProcessor:
        """Create a ProjectWebhookProcessor instance"""
        return ProjectWebhookProcessor(event=mock_event)

    @pytest.fixture
    def project_create_payload(self) -> dict[str, Any]:
        """Create a sample project creation webhook payload"""
        return {
            "event_name": "project_create",
            "created_at": "2021-01-20T09:40:12Z",
            "updated_at": "2021-01-20T09:40:12Z",
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
            "project_id": 12345,
            "project_namespace_id": 67890,
            "project_visibility": "private",
        }

    @pytest.fixture
    def project_destroy_payload(self) -> dict[str, Any]:
        """Create a sample project deletion webhook payload"""
        return {
            "event_name": "project_destroy",
            "created_at": "2021-01-20T09:40:12Z",
            "updated_at": "2021-01-20T09:40:12Z",
            "name": "test-project-deleted-12345",
            "path": "test-project-deleted-12345",
            "path_with_namespace": "group/test-project-deleted-12345",
            "project_id": 12345,
            "project_namespace_id": 67890,
            "project_visibility": "private",
        }

    async def test_get_matching_kinds(
        self, processor: ProjectWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the PROJECT kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.PROJECT]

    async def test_handle_event_project_create(
        self, processor: ProjectWebhookProcessor, project_create_payload: dict[str, Any]
    ) -> None:
        """Test handling a project creation event"""
        resource_config = MagicMock()
        project_id = project_create_payload["project_id"]
        expected_project = {
            "id": project_id,
            "name": project_create_payload["name"],
            "path": project_create_payload["path"],
            "path_with_namespace": project_create_payload["path_with_namespace"],
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(project_create_payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(project_id)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_project
        assert not result.deleted_raw_results

    async def test_handle_event_project_destroy(
        self,
        processor: ProjectWebhookProcessor,
        project_destroy_payload: dict[str, Any],
    ) -> None:
        """Test handling a project deletion event"""
        resource_config = MagicMock()
        expected_deleted_project = {
            "id": project_destroy_payload["project_id"],
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }

        result = await processor.handle_event(project_destroy_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == expected_deleted_project

    async def test_validate_payload_valid(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test payload validation with valid payload"""
        valid_payload = {
            "project_id": 12345,
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }
        assert await processor.validate_payload(valid_payload) is True

    async def test_validate_payload_missing_project_id(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test payload validation with missing project_id"""
        invalid_payload = {"name": "test-project"}
        assert await processor.validate_payload(invalid_payload) is False

    async def test_validate_payload_empty(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test payload validation with empty payload"""
        empty_payload: dict[str, Any] = {}
        assert await processor.validate_payload(empty_payload) is False

    def test_parse_deleted_payload_simple(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "project_id": 12345,
            "name": "test-project-deleted-12345",
            "path": "test-project-deleted-12345",
            "path_with_namespace": "group/test-project-deleted-12345",
        }
        expected = {
            "id": 12345,
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }
        result = processor._parse_deleted_payload(payload)
        assert result == expected

    def test_parse_deleted_payload_complex_name(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "project_id": 67890,
            "name": "my-awesome-project-deleted-67890",
            "path": "my-awesome-project-deleted-67890",
            "path_with_namespace": "my-group/my-awesome-project-deleted-67890",
        }
        expected = {
            "id": 67890,
            "name": "my-awesome-project",
            "path": "my-awesome-project",
            "path_with_namespace": "my-group/my-awesome-project",
        }
        result = processor._parse_deleted_payload(payload)
        assert result == expected

    def test_parse_deleted_payload_no_deleted_suffix(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "project_id": 12345,
            "name": "test-project-12345",
            "path": "test-project-12345",
            "path_with_namespace": "group/test-project-12345",
        }
        expected = {
            "id": 12345,
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }
        result = processor._parse_deleted_payload(payload)
        assert result == expected

    def test_parse_deleted_payload_with_hyphens(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "project_id": 12345,
            "name": "my-project-name-deleted-12345",
            "path": "my-project-name-deleted-12345",
            "path_with_namespace": "my-group/my-project-name-deleted-12345",
        }
        expected = {
            "id": 12345,
            "name": "my-project-name",
            "path": "my-project-name",
            "path_with_namespace": "my-group/my-project-name",
        }
        result = processor._parse_deleted_payload(payload)
        assert result == expected

    def test_parse_deleted_payload_edge_case_single_word(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        payload = {
            "project_id": 12345,
            "name": "project-deleted-12345",
            "path": "project-deleted-12345",
            "path_with_namespace": "group/project-deleted-12345",
        }
        expected = {
            "id": 12345,
            "name": "project",
            "path": "project",
            "path_with_namespace": "group/project",
        }
        result = processor._parse_deleted_payload(payload)
        assert result == expected

    async def test_handle_event_project_create_error(
        self, processor: ProjectWebhookProcessor, project_create_payload: dict[str, Any]
    ) -> None:
        """Test handling project creation when get_project raises an exception"""
        resource_config = MagicMock()
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await processor.handle_event(project_create_payload, resource_config)

    def test_processor_events_attribute(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test that the processor has the correct events attribute"""
        assert processor.events == ["project_create", "project_destroy"]

    def test_processor_hooks_attribute(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test that the processor has the correct hooks attribute"""
        assert processor.hooks == ["Project Hook"]

    async def test_should_process_event_valid(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test should_process_event with valid event"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={"event_name": "project_create"},
        )
        assert await processor.should_process_event(event) is True

    async def test_should_process_event_invalid_hook(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test should_process_event with invalid hook"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Group Hook"},
            payload={"event_name": "project_create"},
        )
        assert await processor.should_process_event(event) is False

    async def test_should_process_event_invalid_event(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test should_process_event with invalid event"""
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={"event_name": "merge_request_create"},
        )
        assert await processor.should_process_event(event) is False
