"""Tests for webhook processors handling search queries enrichment."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from gitlab.webhook.webhook_processors.push_webhook_processor import (
    PushWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from typing import Any

from integration import SearchQuery


@pytest.mark.asyncio
class TestProjectWebhookWithSearchQueries:
    """Test project webhook processor with search queries."""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Project Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> ProjectWebhookProcessor:
        return ProjectWebhookProcessor(event=mock_event)

    async def test_handle_event_with_search_queries(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test that project webhook passes search_queries to get_project."""
        payload = {
            "event_name": "project_create",
            "project_id": 12345,
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }

        search_queries = [
            SearchQuery(name="hasPortYml", scope="blobs", query="filename:port.yml"),
        ]

        resource_config = MagicMock()
        resource_config.selector.include_languages = True
        resource_config.selector.search_queries = search_queries

        expected_project = {
            "id": 12345,
            "name": "test-project",
            "path_with_namespace": "group/test-project",
            "__searchQueries": {"hasPortYml": True},
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(payload, resource_config)

        # Verify search_queries were serialized and passed
        call_kwargs = processor._gitlab_webhook_client.get_project.call_args
        assert call_kwargs[1]["search_queries"] == [
            sq.dict() for sq in search_queries
        ]
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__searchQueries"]["hasPortYml"] is True

    async def test_handle_event_without_search_queries(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test project webhook with empty search_queries passes None."""
        payload = {
            "event_name": "project_create",
            "project_id": 12345,
            "name": "test-project",
            "path": "test-project",
            "path_with_namespace": "group/test-project",
        }

        resource_config = MagicMock()
        resource_config.selector.include_languages = False
        resource_config.selector.search_queries = []

        expected_project = {"id": 12345, "name": "test-project"}

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(
            12345, False, search_queries=None
        )
        assert len(result.updated_raw_results) == 1

    async def test_handle_event_destroy_ignores_search_queries(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test that project_destroy event doesn't try to use search_queries."""
        payload = {
            "event_name": "project_destroy",
            "project_id": 12345,
            "name": "test-project-deleted-12345",
            "path": "test-project-deleted-12345",
            "path_with_namespace": "group/test-project-deleted-12345",
        }

        resource_config = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == 12345


@pytest.mark.asyncio
class TestPushWebhookWithSearchQueries:
    """Test push webhook processor with search queries."""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "push"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PushWebhookProcessor:
        return PushWebhookProcessor(event=mock_event)

    async def test_handle_event_with_search_queries(
        self, processor: PushWebhookProcessor
    ) -> None:
        """Test that push webhook passes search_queries to get_project."""
        payload = {
            "object_kind": "push",
            "event_name": "push",
            "project_id": 123,
            "project": {"id": 123, "name": "test-repo"},
        }

        search_queries = [
            SearchQuery(name="hasCI", scope="blobs", query="filename:.gitlab-ci.yml"),
            SearchQuery(
                name="hasDockerfile", scope="blobs", query="filename:Dockerfile"
            ),
        ]

        resource_config = MagicMock()
        resource_config.selector.search_queries = search_queries

        expected_project = {
            "id": 123,
            "name": "test-repo",
            "__searchQueries": {"hasCI": True, "hasDockerfile": False},
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(payload, resource_config)

        call_kwargs = processor._gitlab_webhook_client.get_project.call_args
        assert call_kwargs[1]["search_queries"] == [
            sq.dict() for sq in search_queries
        ]
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__searchQueries"]["hasCI"] is True
        assert result.updated_raw_results[0]["__searchQueries"]["hasDockerfile"] is False

    async def test_handle_event_without_search_queries(
        self, processor: PushWebhookProcessor
    ) -> None:
        """Test push webhook with empty search_queries passes None."""
        payload = {
            "object_kind": "push",
            "event_name": "push",
            "project": {"id": 456, "name": "test-repo"},
        }

        resource_config = MagicMock()
        resource_config.selector.search_queries = []

        expected_project = {"id": 456, "name": "test-repo"}

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_project
        )

        result = await processor.handle_event(payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(
            456, search_queries=None
        )
        assert len(result.updated_raw_results) == 1
