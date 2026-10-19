import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from unittest.mock import MagicMock

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.pull_request_comment_webhook_processor import (
    PullRequestCommentWebhookProcessor,
)
from integration import (
    GithubPullRequestCommentConfig,
    GithubPullRequestCommentSelector,
)


@pytest.fixture
def resource_config() -> GithubPullRequestCommentConfig:
    return GithubPullRequestCommentConfig(
        kind=ObjectKind.PULL_REQUEST_COMMENT,
        selector=GithubPullRequestCommentSelector(query="true", states=["open"]),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".__commentId",
                    title=".__body",
                    blueprint='"githubPullRequestComment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> PullRequestCommentWebhookProcessor:
    return PullRequestCommentWebhookProcessor(event=mock_webhook_event)


def _payload() -> dict[str, object]:
    return {
        "action": "created",
        "issue": {
            "id": 700,
            "number": 7,
            "state": "open",
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


@pytest.mark.asyncio
class TestPullRequestCommentWebhookProcessor:
    async def test_matches_pull_request_issue_comments(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        event = MagicMock(spec=WebhookEvent)
        event.headers = {"x-github-event": "issue_comment"}
        event.payload = _payload()
        assert await processor._should_process_event(event) is True

    async def test_ignores_issue_comments_that_are_not_on_a_pull_request(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        event = MagicMock(spec=WebhookEvent)
        event.headers = {"x-github-event": "issue_comment"}
        payload = _payload()
        payload["issue"] = {"id": 1, "number": 1, "state": "open"}
        event.payload = payload
        assert await processor._should_process_event(event) is False

    async def test_get_matching_kinds(
        self, processor: PullRequestCommentWebhookProcessor
    ) -> None:
        kinds = await processor.get_matching_kinds(MagicMock(spec=WebhookEvent))
        assert kinds == [ObjectKind.PULL_REQUEST_COMMENT]

    async def test_handle_event_upserts_open_pull_request_comment(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestCommentConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        result = await processor.handle_event(_payload(), resource_config)
        assert result.deleted_raw_results == []
        assert result.updated_raw_results[0]["__commentId"] == "repo1/7/comment/11"
        assert result.updated_raw_results[0]["__pullRequestId"] == 700

    async def test_handle_event_deletes_comment(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestCommentConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "issue_comment"}
        payload = _payload()
        payload["action"] = "deleted"
        result = await processor.handle_event(payload, resource_config)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results[0]["__commentId"] == "repo1/7/comment/11"

    async def test_handle_event_drops_comments_on_untracked_pull_request_state(
        self,
        processor: PullRequestCommentWebhookProcessor,
        resource_config: GithubPullRequestCommentConfig,
    ) -> None:
        processor.event.headers = {"x-github-event": "pull_request_review_comment"}
        payload = {
            "action": "created",
            "pull_request": {"id": 700, "number": 7, "state": "closed"},
            "comment": {
                "id": 22,
                "body": "Rename this",
                "user": {"login": "reviewer"},
                "created_at": "2026-10-01T01:00:00Z",
                "html_url": "https://github.com/test-org/repo1/pull/7#discussion_r22",
            },
            "repository": {"name": "repo1"},
            "organization": {"login": "test-org"},
        }
        result = await processor.handle_event(payload, resource_config)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results[0]["__commentType"] == "review"
