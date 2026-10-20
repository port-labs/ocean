from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.pull_request_comment_webhook_processor import (
    PullRequestCommentWebhookProcessor,
)
from integration import GithubPullRequestConfig, GithubPullRequestSelector


def _recent_updated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
            includeComments=True,
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def resource_config_comments_off() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
            includeComments=False,
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> PullRequestCommentWebhookProcessor:
    return PullRequestCommentWebhookProcessor(event=mock_webhook_event)


def _issue_comment_payload() -> dict[str, Any]:
    return {
        "action": "created",
        "issue": {
            "id": 700,
            "number": 7,
            "state": "open",
            "updated_at": _recent_updated_at(),
            "pull_request": {
                "url": "https://api.github.com/repos/test-org/repo1/pulls/7"
            },
        },
        "comment": {
            "id": 11,
            "body": "Please add a test",
            "html_url": "https://github.com/test-org/repo1/pull/7#issuecomment-11",
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": "2026-10-02T00:00:00Z",
            "user": {"login": "reviewer"},
        },
        "repository": {"name": "repo1", "full_name": "test-org/repo1"},
        "organization": {"login": "test-org"},
    }


def _fetched_pull_request() -> dict[str, Any]:
    return {
        "id": 700,
        "number": 7,
        "title": "Fix tests",
        "state": "open",
        "updated_at": _recent_updated_at(),
        "__repository": "repo1",
        "__organization": "test-org",
        "head": {"repo": {"name": "repo1"}},
    }


@pytest.mark.asyncio
class TestPullRequestCommentWebhookProcessor:
    async def test_matches_pull_request_issue_comments(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        event = MagicMock(spec=WebhookEvent)
        event.headers = {"x-github-event": "issue_comment"}
        event.payload = _issue_comment_payload()
        assert await processor._should_process_event(event) is True

    async def test_ignores_issue_comments_that_are_not_on_a_pull_request(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        event = MagicMock(spec=WebhookEvent)
        event.headers = {"x-github-event": "issue_comment"}
        payload = _issue_comment_payload()
        payload["issue"] = {
            "id": 1,
            "number": 1,
            "state": "open",
            "updated_at": _recent_updated_at(),
        }
        event.payload = payload
        assert await processor._should_process_event(event) is False

    async def test_get_matching_kinds_returns_pull_request(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        kinds = await processor.get_matching_kinds(MagicMock(spec=WebhookEvent))
        assert kinds == [ObjectKind.PULL_REQUEST]

    async def test_handle_event_noops_when_include_comments_false(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config_comments_off: GithubPullRequestConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        with (
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
            ) as mock_client,
            patch.object(
                processor, "should_process_repo_search", AsyncMock(return_value=True)
            ),
        ):
            result = await processor.handle_event(
                _issue_comment_payload(), resource_config_comments_off
            )

        mock_client.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_returns_pull_request_with_comments_when_enabled(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        fetched_pr = _fetched_pull_request()
        comments = [
            {
                "id": 11,
                "body": "Please add a test",
                "html_url": "https://github.com/test-org/repo1/pull/7#issuecomment-11",
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-02T00:00:00Z",
                "user": {"login": "reviewer"},
                "__commentId": "repo1/7/comment/11",
                "__commentType": "comment",
            }
        ]

        mock_pr_exporter = MagicMock()
        mock_pr_exporter.get_resource = AsyncMock(return_value=fetched_pr)
        mock_comment_exporter = MagicMock()
        mock_comment_exporter.enrich_pull_requests = AsyncMock(
            return_value=[{**fetched_pr, "__comments": comments}]
        )

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestExporter",
                return_value=mock_pr_exporter,
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestCommentExporter",
                return_value=mock_comment_exporter,
            ),
            patch.object(
                processor, "should_process_repo_search", AsyncMock(return_value=True)
            ),
        ):
            result = await processor.handle_event(
                _issue_comment_payload(), resource_config
            )

        assert result.deleted_raw_results == []
        assert len(result.updated_raw_results) == 1
        updated = result.updated_raw_results[0]
        assert updated["id"] == 700
        assert updated["__comments"] == comments
        mock_comment_exporter.enrich_pull_requests.assert_awaited_once()

    async def test_handle_event_deleted_comment_still_returns_pr_with_comments(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        payload = _issue_comment_payload()
        payload["action"] = "deleted"
        fetched_pr = _fetched_pull_request()
        remaining_comments: list[dict[str, Any]] = []

        mock_pr_exporter = MagicMock()
        mock_pr_exporter.get_resource = AsyncMock(return_value=fetched_pr)
        mock_comment_exporter = MagicMock()
        mock_comment_exporter.enrich_pull_requests = AsyncMock(
            return_value=[{**fetched_pr, "__comments": remaining_comments}]
        )

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestExporter",
                return_value=mock_pr_exporter,
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestCommentExporter",
                return_value=mock_comment_exporter,
            ),
            patch.object(
                processor, "should_process_repo_search", AsyncMock(return_value=True)
            ),
        ):
            result = await processor.handle_event(payload, resource_config)

        assert result.deleted_raw_results == []
        assert result.updated_raw_results[0]["__comments"] == []

    async def test_handle_event_fetches_comments_when_pr_updated_at_is_old(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        payload = _issue_comment_payload()
        payload["issue"]["updated_at"] = "2020-01-01T00:00:00Z"
        fetched_pr = _fetched_pull_request()
        fetched_pr["updated_at"] = "2020-01-01T00:00:00Z"
        comments = [
            {
                "id": 11,
                "body": "Please add a test",
                "user": {"login": "reviewer"},
                "__commentId": "repo1/7/comment/11",
                "__commentType": "comment",
            }
        ]

        mock_pr_exporter = MagicMock()
        mock_pr_exporter.get_resource = AsyncMock(return_value=fetched_pr)
        mock_comment_exporter = MagicMock()
        mock_comment_exporter.enrich_pull_requests = AsyncMock(
            return_value=[{**fetched_pr, "__comments": comments}]
        )

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestExporter",
                return_value=mock_pr_exporter,
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_comment_webhook_processor.RestPullRequestCommentExporter",
                return_value=mock_comment_exporter,
            ),
            patch.object(
                processor, "should_process_repo_search", AsyncMock(return_value=True)
            ),
        ):
            result = await processor.handle_event(payload, resource_config)

        assert result.deleted_raw_results == []
        assert result.updated_raw_results[0]["__comments"] == comments
        mock_comment_exporter.enrich_pull_requests.assert_awaited_once()
