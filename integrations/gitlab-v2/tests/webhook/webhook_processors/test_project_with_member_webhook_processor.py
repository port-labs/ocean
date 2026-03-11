import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.project_with_member_webhook_processor import (
    ProjectWithMemberWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestProjectWithMemberWebhookProcessor:
    """Test the project with member webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> ProjectWithMemberWebhookProcessor:
        """Create a ProjectWithMemberWebhookProcessor instance"""
        return ProjectWithMemberWebhookProcessor(event=mock_event)

    @pytest.fixture
    def project_create_payload(self) -> dict[str, Any]:
        return {
            "event_name": "project_create",
            "project_id": 74,
            "name": "my-project",
            "path": "my-project",
            "path_with_namespace": "group1/my-project",
        }

    @pytest.fixture
    def project_destroy_payload(self) -> dict[str, Any]:
        return {
            "event_name": "project_destroy",
            "project_id": 74,
            "name": "my-project-deleted-74",
            "path": "my-project-deleted-74",
            "path_with_namespace": "group1/my-project-deleted-74",
        }

    @pytest.fixture
    def member_add_payload(self) -> dict[str, Any]:
        return {
            "event_name": "user_add_to_team",
            "project_id": 74,
            "user_username": "jsmith",
            "user_id": 41,
        }

    @pytest.fixture
    def member_remove_payload(self) -> dict[str, Any]:
        return {
            "event_name": "user_remove_from_team",
            "project_id": 74,
            "user_username": "jsmith",
            "user_id": 41,
        }

    async def test_get_matching_kinds(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        mock_event: WebhookEvent,
    ) -> None:
        assert await processor.get_matching_kinds(mock_event) == [
            ObjectKind.PROJECT_WITH_MEMBERS
        ]

    async def test_handle_project_create_event(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        project_create_payload: dict[str, Any],
    ) -> None:
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = True
        resource_config.selector.include_inherited_members = False

        project_id = project_create_payload["project_id"]
        expected_project = {
            "id": project_id,
            "name": "my-project",
            "path_with_namespace": "group1/my-project",
            "__members": [
                {"id": 1, "username": "user1", "name": "User One"},
            ],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value={
                "id": project_id,
                "name": "my-project",
                "path_with_namespace": "group1/my-project",
            }
        )
        processor._gitlab_webhook_client.enrich_project_with_members = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(project_create_payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(project_id)
        processor._gitlab_webhook_client.enrich_project_with_members.assert_called_once_with(
            {
                "id": project_id,
                "name": "my-project",
                "path_with_namespace": "group1/my-project",
            },
            include_bot_members=True,
            include_inherited_members=False,
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_project
        assert not result.deleted_raw_results

    async def test_handle_project_destroy_event(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        project_destroy_payload: dict[str, Any],
    ) -> None:
        resource_config = MagicMock()

        result = await processor.handle_event(project_destroy_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["id"] == 74
        assert deleted["name"] == "my-project"
        assert deleted["path"] == "my-project"
        assert deleted["path_with_namespace"] == "group1/my-project"

    async def test_handle_member_add_event(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        member_add_payload: dict[str, Any],
    ) -> None:
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = False
        resource_config.selector.include_inherited_members = True

        expected_project = {
            "id": 74,
            "name": "my-project",
            "__members": [
                {"id": 41, "username": "jsmith", "name": "John Smith"},
            ],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value={"id": 74, "name": "my-project"}
        )
        processor._gitlab_webhook_client.enrich_project_with_members = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(member_add_payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(74)
        processor._gitlab_webhook_client.enrich_project_with_members.assert_called_once_with(
            {"id": 74, "name": "my-project"},
            include_bot_members=False,
            include_inherited_members=True,
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_project
        assert not result.deleted_raw_results

    async def test_handle_member_remove_event(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        member_remove_payload: dict[str, Any],
    ) -> None:
        """Member removal re-fetches the project with updated members list."""
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = True
        resource_config.selector.include_inherited_members = False

        expected_project = {"id": 74, "name": "my-project", "__members": []}

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value={"id": 74, "name": "my-project"}
        )
        processor._gitlab_webhook_client.enrich_project_with_members = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(member_remove_payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__members"] == []
        assert not result.deleted_raw_results

    async def test_handle_event_project_not_found(
        self,
        processor: ProjectWithMemberWebhookProcessor,
        member_add_payload: dict[str, Any],
    ) -> None:
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = True
        resource_config.selector.include_inherited_members = False

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(return_value=None)

        result = await processor.handle_event(member_add_payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {}
        assert not result.deleted_raw_results

    async def test_should_process_event(
        self, processor: ProjectWithMemberWebhookProcessor
    ) -> None:
        valid_project_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={"event_name": "project_create"},
        )
        assert await processor.should_process_event(valid_project_event) is True

        valid_member_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Member Hook"},
            payload={"event_name": "user_add_to_team"},
        )
        assert await processor.should_process_event(valid_member_event) is True

        invalid_hook = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"event_name": "project_create"},
        )
        assert await processor.should_process_event(invalid_hook) is False

        invalid_event_name = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={"event_name": "pipeline_success"},
        )
        assert await processor.should_process_event(invalid_event_name) is False

    async def test_validate_payload(
        self, processor: ProjectWithMemberWebhookProcessor
    ) -> None:
        valid_project_payload = {
            "project_id": 74,
            "event_name": "project_create",
            "name": "my-project",
            "path": "my-project",
            "path_with_namespace": "group1/my-project",
        }
        assert await processor.validate_payload(valid_project_payload) is True

        valid_member_payload = {
            "project_id": 74,
            "event_name": "user_add_to_team",
            "user_username": "jsmith",
        }
        assert await processor.validate_payload(valid_member_payload) is True

        missing_project_id = {"event_name": "project_create"}
        assert await processor.validate_payload(missing_project_id) is False

        missing_event_name = {"project_id": 74}
        assert await processor.validate_payload(missing_event_name) is False

        destroy_missing_name = {
            "project_id": 74,
            "event_name": "project_destroy",
            "path": "my-project",
            "path_with_namespace": "group1/my-project",
        }
        assert await processor.validate_payload(destroy_missing_name) is False

        valid_destroy_payload = {
            "project_id": 74,
            "event_name": "project_destroy",
            "name": "my-project-deleted-74",
            "path": "my-project-deleted-74",
            "path_with_namespace": "group1/my-project-deleted-74",
        }
        assert await processor.validate_payload(valid_destroy_payload) is True
