import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.issue import IssueWebhookProcessor
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
        kind=ObjectKind.ISSUE,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='(.repository.full_name | gsub("/"; "-")) + "-issue-" + (.number | tostring)',
                    title=".title",
                    blueprint='"githubIssue"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    @pytest.fixture
    def issue_webhook_processor(
        self, mock_webhook_event: WebhookEvent
    ) -> IssueWebhookProcessor:
        return IssueWebhookProcessor(event=mock_webhook_event)

    async def test_should_process_event_opened(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "opened", "issue": {}},
            headers={"X-GitHub-Event": "issues"},
        )
        result = await issue_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_closed(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "closed", "issue": {}},
            headers={"X-GitHub-Event": "issues"},
        )
        result = await issue_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_not_process_invalid_event_type(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "opened", "issue": {}},
            headers={"X-GitHub-Event": "pull_request"},
        )
        result = await issue_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_event_create_success(
        self,
        issue_webhook_processor: IssueWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        issue_data = {
            "id": 1,
            "number": 123,
            "title": "Test Issue",
            "state": "open",
            "repository": {"name": "test-repo"},
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = issue_data

        with patch(
            "webhook_processors.issue.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await issue_webhook_processor.handle_event(
                {
                    "action": "opened",
                    "issue": {"number": 123},
                    "repository": {"name": "test-repo"},
                },
                resource_config,
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [issue_data]
        assert result.deleted_raw_results == []
        mock_client.get_single_resource.assert_called_once_with(
            ObjectKind.ISSUE, "test-repo/123"
        )

    async def test_handle_event_api_error(
        self,
        issue_webhook_processor: IssueWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.side_effect = Exception("API Error")

        with patch(
            "webhook_processors.issue.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            with pytest.raises(Exception, match="API Error"):
                await issue_webhook_processor.handle_event(
                    {
                        "action": "opened",
                        "issue": {"number": 123},
                        "repository": {"name": "test-repo"},
                    },
                    resource_config,
                )
