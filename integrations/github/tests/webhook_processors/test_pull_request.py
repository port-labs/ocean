import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.pull_request import PullRequestWebhookProcessor
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
        kind=ObjectKind.PULL_REQUEST,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id|tostring",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestPullRequestWebhookProcessor:
    @pytest.fixture
    def pull_request_webhook_processor(
        self, mock_webhook_event: WebhookEvent
    ) -> PullRequestWebhookProcessor:
        return PullRequestWebhookProcessor(event=mock_webhook_event)

    @pytest.mark.parametrize("action", ["opened", "closed", "reopened", "edited"])
    async def test_should_process_valid_events(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor, action: str
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action, "pull_request": {}},
            headers={"x-github-event": "pull_request"},
        )
        result = await pull_request_webhook_processor.should_process_event(event)
        assert result is True

    async def test_handle_event_success(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        pr_data = {
            "id": 1,
            "number": 456,
            "title": "Test PR",
            "state": "open",
            "merged": False,
            "head": {"ref": "feature-branch"},
            "base": {"ref": "main"},
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = pr_data

        with patch(
            "webhook_processors.pull_request.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await pull_request_webhook_processor.handle_event(
                {
                    "action": "opened",
                    "pull_request": {"number": 456},
                    "repository": {"name": "test-repo"},
                },
                resource_config,
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [pr_data]
        assert result.deleted_raw_results == []
        mock_client.get_single_resource.assert_called_once_with(
            ObjectKind.PULL_REQUEST, "test-repo/456"
        )
