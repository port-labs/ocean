from typing import Any, AsyncGenerator

import pytest
from unittest.mock import AsyncMock, patch

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pull_request_comment_exporter import (
    RestPullRequestCommentExporter,
    normalize_pull_request_comment,
)
from github.core.options import (
    ListPullRequestCommentOptions,
    SinglePullRequestCommentOptions,
)


def _async_batches(
    *batches: list[dict[str, Any]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async def generator() -> AsyncGenerator[list[dict[str, Any]], None]:
        for batch in batches:
            yield batch

    return generator()


CONVERSATION = {
    "id": 11,
    "body": "Please add a test",
    "html_url": "https://github.com/test-org/repo1/pull/7#issuecomment-11",
    "created_at": "2026-10-01T00:00:00Z",
    "updated_at": "2026-10-02T00:00:00Z",
    "user": {"login": "reviewer"},
}
INLINE = {
    "id": 22,
    "body": "Rename this",
    "html_url": "https://github.com/test-org/repo1/pull/7#discussion_r22",
    "created_at": "2026-10-01T01:00:00Z",
    "updated_at": "2026-10-01T01:00:00Z",
    "user": {"login": "reviewer"},
}
REVIEW = {
    "id": 33,
    "body": "Changes requested",
    "html_url": "https://github.com/test-org/repo1/pull/7#pullrequestreview-33",
    "submitted_at": "2026-10-01T02:00:00Z",
    "user": {"login": "reviewer"},
}
EMPTY_REVIEW = {"id": 34, "body": "  ", "user": {"login": "reviewer"}}


@pytest.mark.asyncio
class TestPullRequestCommentExporter:
    async def test_get_resource_normalizes_conversation_comment(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestCommentExporter(rest_client)
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=CONVERSATION)
        ) as mock_request:
            comment = await exporter.get_resource(
                SinglePullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                    comment_id=11,
                    comment_type="comment",
                )
            )

        assert comment is not None
        assert comment["__commentId"] == "repo1/7/comment/11"
        assert comment["__commentType"] == "comment"
        assert comment["__author"] == "reviewer"
        assert comment["__pullRequestId"] == 700
        assert comment["__repository"] == "repo1"
        assert comment["__organization"] == "test-org"
        mock_request.assert_called_once_with(
            f"{rest_client.base_url}/repos/test-org/repo1/issues/7/comments/11"
        )

    async def test_get_resource_skips_empty_review_summary(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestCommentExporter(rest_client)
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=EMPTY_REVIEW)
        ):
            comment = await exporter.get_resource(
                SinglePullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                    comment_id=34,
                    comment_type="review-summary",
                )
            )
        assert comment is None

    async def test_get_paginated_resources_yields_all_comment_types(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestCommentExporter(rest_client)

        def mock_paginated(
            url: str, params: dict[str, Any] | None = None
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if url.endswith("/issues/7/comments"):
                return _async_batches([CONVERSATION])
            if url.endswith("/pulls/7/comments"):
                return _async_batches([INLINE])
            if url.endswith("/pulls/7/reviews"):
                return _async_batches([REVIEW, EMPTY_REVIEW])
            raise AssertionError(url)

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            comments = []
            async for batch in exporter.get_paginated_resources(
                ListPullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                )
            ):
                comments.extend(batch)

        assert [comment["__commentId"] for comment in comments] == [
            "repo1/7/comment/11",
            "repo1/7/review/22",
            "repo1/7/review-summary/33",
        ]
        assert comments[2]["__createdAt"] == "2026-10-01T02:00:00Z"
        assert comments[2]["__body"] == "Changes requested"


def test_normalize_pull_request_comment_uses_submitted_at_for_reviews() -> None:
    normalized = normalize_pull_request_comment(
        REVIEW,
        organization="test-org",
        repo_name="repo1",
        pull_request_id=700,
        pull_request_number=7,
        comment_type="review-summary",
    )
    assert normalized["__createdAt"] == "2026-10-01T02:00:00Z"
    assert normalized["__updatedAt"] == "2026-10-01T02:00:00Z"
    assert normalized["__url"].endswith("#pullrequestreview-33")
