import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.repository import RepositoryWebhookProcessor
from client import GitHubClient

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.REPOSITORY,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestRepositoryWebhookProcessor:
    @pytest.fixture
    def repository_webhook_processor(
        self, mock_webhook_event: WebhookEvent
    ) -> RepositoryWebhookProcessor:
        return RepositoryWebhookProcessor(event=mock_webhook_event)

    async def test_should_process_event_create(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "created", "repository": {}},
            headers={"x-github-event": "repository"},
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_delete(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "deleted", "repository": {}},
            headers={"x-github-event": "repository"},
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_not_process_invalid_event_type(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "created", "repository": {}},
            headers={"x-github-event": "issues"},
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is False

    async def test_should_not_process_invalid_action(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "invalid_action", "repository": {}},
            headers={"x-github-event": "repository"},
        )
        result = await repository_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_event_create_success(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "test-org/test-repo",
            "description": "Test repository",
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = repo_data

        with patch(
            "webhook_processors.repository.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await repository_webhook_processor.handle_event(
                {"action": "created", "repository": {"name": "test-repo"}},
                resource_config,
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [repo_data]
        assert result.deleted_raw_results == []
        mock_client.get_single_resource.assert_called_once_with(
            ObjectKind.REPOSITORY, "test-repo"
        )

    async def test_handle_event_delete(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        repo_data = {"id": 1, "name": "test-repo", "full_name": "test-org/test-repo"}

        result = await repository_webhook_processor.handle_event(
            {"action": "deleted", "repository": repo_data}, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [repo_data]

    async def test_handle_event_api_error(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.side_effect = Exception("API Error")

        with patch(
            "webhook_processors.repository.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            with pytest.raises(Exception, match="API Error"):
                await repository_webhook_processor.handle_event(
                    {"action": "created", "repository": {"name": "test-repo"}},
                    resource_config,
                )

    async def test_handle_event_missing_data(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        with pytest.raises(KeyError):
            await repository_webhook_processor.handle_event(
                {"action": "created"}, resource_config  # Missing repository data
            )
