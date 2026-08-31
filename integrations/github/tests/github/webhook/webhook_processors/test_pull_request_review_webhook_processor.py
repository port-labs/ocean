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

from github.webhook.webhook_processors.pull_request_review_webhook_processor import (
    PullRequestReviewWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import PULL_REQUEST_REVIEW_EVENTS
from github.core.options import SinglePullRequestOptions
from integration import GithubPullRequestSelector, GithubPullRequestConfig


@pytest.fixture
def pull_request_review_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PullRequestReviewWebhookProcessor:
    return PullRequestReviewWebhookProcessor(event=mock_webhook_event)


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
class TestPullRequestReviewWebhookProcessor:
    async def test_should_process_event_valid(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request_review"}
        mock_event.payload = {"action": "submitted"}

        assert (
            await pull_request_review_webhook_processor._should_process_event(
                mock_event
            )
            is True
        )

    async def test_should_process_event_wrong_header(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request"}
        mock_event.payload = {"action": "submitted"}

        assert (
            await pull_request_review_webhook_processor._should_process_event(
                mock_event
            )
            is False
        )

    async def test_should_process_event_wrong_action(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request_review"}
        mock_event.payload = {"action": "created"}

        assert (
            await pull_request_review_webhook_processor._should_process_event(
                mock_event
            )
            is False
        )

    async def test_validate_payload_valid(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        for action in PULL_REQUEST_REVIEW_EVENTS:
            payload = {
                "action": action,
                "pull_request": {"number": 101},
                "repository": {"name": "test-repo"},
                "review": {"id": 1, "state": "approved"},
            }
            assert (
                await pull_request_review_webhook_processor._validate_payload(payload)
                is True
            )

    async def test_validate_payload_missing_review(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        payload = {
            "action": "submitted",
            "pull_request": {"number": 101},
            "repository": {"name": "test-repo"},
        }
        assert (
            await pull_request_review_webhook_processor._validate_payload(payload)
            is False
        )

    async def test_validate_payload_missing_pull_request(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        payload = {
            "action": "submitted",
            "repository": {"name": "test-repo"},
            "review": {"id": 1, "state": "approved"},
        }
        assert (
            await pull_request_review_webhook_processor._validate_payload(payload)
            is False
        )

    async def test_get_matching_kinds(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await pull_request_review_webhook_processor.get_matching_kinds(
            mock_event
        )
        assert kinds == [ObjectKind.PULL_REQUEST]

    async def test_handle_event_upserts_pr(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        pr_data = {
            "id": 1,
            "number": 101,
            "title": "Test PR",
            "state": "open",
        }
        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}
        payload = {
            "action": "submitted",
            "pull_request": pr_data,
            "repository": repo_data,
            "organization": {"login": "test-org"},
            "review": {"id": 1, "state": "approved"},
        }

        updated_pr_data = {**pr_data, "additional_data": "from_api"}
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_pr_data

        with patch(
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.RestPullRequestExporter",
            return_value=mock_exporter,
        ):
            result = await pull_request_review_webhook_processor.handle_event(
                payload, resource_config
            )

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [updated_pr_data]
            assert result.deleted_raw_results == []
            mock_exporter.get_resource.assert_called_once_with(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    pr_number=101,
                    repo=None,
                    enrich_with_first_commit=False,
                    exclude_graphql_fields=[],
                )
            )

    async def test_handle_event_deletes_closed_pr_excluded_by_states(
        self,
        pull_request_review_webhook_processor: PullRequestReviewWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        """Review on a closed PR when states=["open"] should delete, not upsert."""
        pr_data = {
            "id": 1,
            "number": 101,
            "title": "Test PR",
            "state": "open",
        }
        payload = {
            "action": "submitted",
            "pull_request": pr_data,
            "repository": {"name": "test-repo", "full_name": "test-org/test-repo"},
            "organization": {"login": "test-org"},
            "review": {"id": 1, "state": "approved"},
        }

        fetched_pr_data = {**pr_data, "state": "closed", "additional_data": "from_api"}
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = fetched_pr_data

        with patch(
            "github.webhook.webhook_processors.base_pull_request_webhook_processor.RestPullRequestExporter",
            return_value=mock_exporter,
        ):
            result = await pull_request_review_webhook_processor.handle_event(
                payload, resource_config
            )

            assert result.updated_raw_results == []
            assert result.deleted_raw_results == [fetched_pr_data]
