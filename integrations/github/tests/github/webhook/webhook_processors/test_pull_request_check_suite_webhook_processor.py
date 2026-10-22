from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.pull_request_check_suite_webhook_processor import (
    PullRequestCheckSuiteWebhookProcessor,
)
from integration import GithubPullRequestConfig, GithubPullRequestSelector


@pytest.fixture
def pull_request_check_suite_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PullRequestCheckSuiteWebhookProcessor:
    return PullRequestCheckSuiteWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
            api="rest",
        ),
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
class TestPullRequestCheckSuiteWebhookProcessor:
    async def test_should_process_event_valid(
        self,
        pull_request_check_suite_webhook_processor: PullRequestCheckSuiteWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "check_suite"}
        mock_event.payload = {"action": "completed"}

        assert (
            await pull_request_check_suite_webhook_processor._should_process_event(
                mock_event
            )
            is True
        )

    async def test_should_process_event_wrong_header(
        self,
        pull_request_check_suite_webhook_processor: PullRequestCheckSuiteWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request"}
        mock_event.payload = {"action": "completed"}

        assert (
            await pull_request_check_suite_webhook_processor._should_process_event(
                mock_event
            )
            is False
        )

    async def test_handle_event_refreshes_linked_pull_requests(
        self,
        pull_request_check_suite_webhook_processor: PullRequestCheckSuiteWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        payload = {
            "action": "completed",
            "check_suite": {
                "pull_requests": [{"number": 7}, {"number": 8}],
            },
            "repository": {"name": "repo1"},
            "organization": {"login": "org1"},
        }
        refreshed = WebhookEventRawResults(
            updated_raw_results=[{"number": 7, "checks_status": "failure"}],
            deleted_raw_results=[],
        )

        with (
            patch.object(
                pull_request_check_suite_webhook_processor,
                "should_process_repo_search",
                new=AsyncMock(return_value=True),
            ),
            patch.object(
                pull_request_check_suite_webhook_processor,
                "get_webhook_payload_organization",
                return_value={"login": "org1"},
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_check_suite_webhook_processor.BasePullRequestWebhookProcessor.handle_event",
                new=AsyncMock(return_value=refreshed),
            ) as mock_handle,
        ):
            result = await pull_request_check_suite_webhook_processor.handle_event(
                payload, resource_config
            )

        assert mock_handle.await_count == 2
        assert len(result.updated_raw_results) == 2
        assert result.deleted_raw_results == []

    async def test_handle_event_skips_when_no_linked_prs(
        self,
        pull_request_check_suite_webhook_processor: PullRequestCheckSuiteWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        payload = {
            "action": "completed",
            "check_suite": {"pull_requests": []},
            "repository": {"name": "repo1"},
            "organization": {"login": "org1"},
        }

        with patch.object(
            pull_request_check_suite_webhook_processor,
            "get_webhook_payload_organization",
            return_value={"login": "org1"},
        ):
            result = await pull_request_check_suite_webhook_processor.handle_event(
                payload, resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
