from typing import Literal
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)

from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import PULL_REQUEST_EVENTS
from github.core.options import SinglePullRequestOptions
from integration import GithubPullRequestSelector, GithubPullRequestConfig


@pytest.fixture
def pull_request_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PullRequestWebhookProcessor:
    return PullRequestWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind="pull-request",
        selector=GithubPullRequestSelector(query="true", state="open"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".head.repo.name + (.id|tostring)",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestPullRequestWebhookProcessor:
    async def test_should_process_event_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request"}
        mock_event.payload = {"action": "opened"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is True
        )

    async def test_should_process_event_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "some_other_event"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_get_matching_kinds(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await pull_request_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.PULL_REQUEST]

    async def test_validate_payload_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Valid upsert payload
        for action in PULL_REQUEST_EVENTS:
            payload = {
                "action": action,
                "pull_request": {"number": 101},
                "repository": {"name": "test-repo"},
            }
            assert (
                await pull_request_webhook_processor._validate_payload(payload) is True
            )

    async def test_validate_payload_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Missing pull_request
        payload = {"action": "opened", "repository": {"name": "test-repo"}}
        assert await pull_request_webhook_processor._validate_payload(payload) is False

        # Missing pull request number
        payload = {
            "action": "opened",
            "pull_request": {},
            "repository": {"name": "test-repo"},
        }
        assert await pull_request_webhook_processor._validate_payload(payload) is False

    @pytest.mark.parametrize(
        "selector_state,action,expected_update,expected_delete",
        [
            ("open", "opened", True, False),
            ("open", "closed", False, True),
            ("closed", "opened", True, False),
            ("closed", "closed", True, False),
            ("all", "opened", True, False),
            ("all", "closed", True, False),
        ],
    )
    async def test_handle_event_with_selector_state(
        self,
        selector_state: Literal["open", "closed", "all"],
        action: str,
        expected_update: bool,
        expected_delete: bool,
        resource_config: GithubPullRequestConfig,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
    ) -> None:
        # Configure resource_config with the specified selector state
        resource_config.selector.state = selector_state

        # Test pull request data
        pr_data = {
            "id": 1,
            "number": 101,
            "title": "Test PR",
            "state": "open" if action == "opened" else "closed",
        }

        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}

        payload = {"action": action, "pull_request": pr_data, "repository": repo_data}

        # Create updated PR data that would be returned by the exporter
        updated_pr_data = {**pr_data, "additional_data": "from_api"}

        # Mock the exporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_pr_data

        with patch(
            "github.webhook.webhook_processors.pull_request_webhook_processor.RestPullRequestExporter",
            return_value=mock_exporter,
        ):
            result = await pull_request_webhook_processor.handle_event(
                payload, resource_config
            )

            # Verify results based on expected behavior
            assert isinstance(result, WebhookEventRawResults)

            if expected_update:
                assert result.updated_raw_results == [updated_pr_data]
                assert result.deleted_raw_results == []
                mock_exporter.get_resource.assert_called_once_with(
                    SinglePullRequestOptions(repo_name="test-repo", pr_number=101)
                )
            elif expected_delete:
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == [pr_data]
                # Should not call get_resource when deleting
                mock_exporter.get_resource.assert_not_called()
