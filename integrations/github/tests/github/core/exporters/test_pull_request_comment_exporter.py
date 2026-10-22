from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pull_request_exporter.utils import (
    attach_pull_request_comments,
    get_pull_request_comment,
    iter_pull_request_comments,
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


def _recent_updated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _old_updated_at(days: int = 60) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _mock_paginated_for_pr_7(
    url: str, params: dict[str, Any] | None = None
) -> AsyncGenerator[list[dict[str, Any]], None]:
    if url.endswith("/issues/7/comments"):
        return _async_batches([CONVERSATION])
    if url.endswith("/pulls/7/comments"):
        return _async_batches([INLINE])
    if url.endswith("/pulls/7/reviews"):
        return _async_batches([REVIEW, EMPTY_REVIEW])
    raise AssertionError(url)


@pytest.mark.asyncio
class TestPullRequestCommentExporter:
    async def test_get_resource_normalizes_conversation_comment(
        self, rest_client: GithubRestClient
    ) -> None:
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=CONVERSATION)
        ) as mock_request:
            comment = await get_pull_request_comment(
                rest_client,
                SinglePullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                    comment_id=11,
                    comment_type="comment",
                ),
            )

        assert comment is not None
        assert comment["__commentId"] == "repo1/7/comment/11"
        assert comment["__commentType"] == "comment"
        assert comment["body"] == "Please add a test"
        assert comment["user"]["login"] == "reviewer"
        assert comment["created_at"] == "2026-10-01T00:00:00Z"
        assert comment["html_url"].endswith("#issuecomment-11")
        assert "__body" not in comment
        assert "__author" not in comment
        mock_request.assert_called_once_with(
            f"{rest_client.base_url}/repos/test-org/repo1/issues/comments/11"
        )

    async def test_get_resource_keeps_empty_review_summary(
        self, rest_client: GithubRestClient
    ) -> None:
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=EMPTY_REVIEW)
        ):
            comment = await get_pull_request_comment(
                rest_client,
                SinglePullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                    comment_id=34,
                    comment_type="review-summary",
                ),
            )
        assert comment is not None
        assert comment["__commentId"] == "repo1/7/review-summary/34"
        assert comment["body"] == "  "

    async def test_get_paginated_resources_yields_all_comment_types(
        self, rest_client: GithubRestClient
    ) -> None:
        with patch.object(
            rest_client, "send_paginated_request", side_effect=_mock_paginated_for_pr_7
        ):
            comments = []
            async for batch in iter_pull_request_comments(
                rest_client,
                ListPullRequestCommentOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    pull_request_id=700,
                ),
            ):
                comments.extend(batch)

        assert [comment["__commentId"] for comment in comments] == [
            "repo1/7/comment/11",
            "repo1/7/review/22",
            "repo1/7/review-summary/33",
            "repo1/7/review-summary/34",
        ]
        assert comments[2]["submitted_at"] == "2026-10-01T02:00:00Z"
        assert "created_at" not in comments[2]
        assert comments[2]["body"] == "Changes requested"

    async def test_attach_comments_includes_every_type_and_empty_review(
        self, rest_client: GithubRestClient
    ) -> None:
        pull_request = {
            "id": 700,
            "number": 7,
            "updated_at": _recent_updated_at(),
            "__repository": "repo1",
            "__organization": "test-org",
        }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=_mock_paginated_for_pr_7
        ) as mock_request:
            enriched = await attach_pull_request_comments(
                rest_client,
                [pull_request],
                organization="test-org",
            )

        assert mock_request.call_count == 3
        assert "__comments" in enriched[0]
        assert [c["__commentId"] for c in enriched[0]["__comments"]] == [
            "repo1/7/comment/11",
            "repo1/7/review/22",
            "repo1/7/review-summary/33",
            "repo1/7/review-summary/34",
        ]

    async def test_attach_comments_fetches_when_pr_updated_at_is_old(
        self, rest_client: GithubRestClient
    ) -> None:
        pull_request = {
            "id": 700,
            "number": 7,
            "updated_at": _old_updated_at(60),
            "__repository": "repo1",
        }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=_mock_paginated_for_pr_7
        ) as mock_request:
            enriched = await attach_pull_request_comments(
                rest_client,
                [pull_request],
                organization="test-org",
            )

        assert mock_request.call_count == 3
        assert "__comments" in enriched[0]
        assert len(enriched[0]["__comments"]) == 4

    async def test_attach_comments_fetches_when_updated_at_missing(
        self, rest_client: GithubRestClient
    ) -> None:
        pull_request = {"id": 700, "number": 7, "__repository": "repo1"}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=_mock_paginated_for_pr_7
        ) as mock_request:
            enriched = await attach_pull_request_comments(
                rest_client,
                [pull_request],
                organization="test-org",
            )

        assert mock_request.call_count == 3
        assert "__comments" in enriched[0]
        assert len(enriched[0]["__comments"]) == 4

    async def test_attach_comments_fetches_when_updated_at_unparseable(
        self, rest_client: GithubRestClient
    ) -> None:
        pull_request = {
            "id": 700,
            "number": 7,
            "updated_at": "not-a-date",
            "__repository": "repo1",
        }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=_mock_paginated_for_pr_7
        ) as mock_request:
            enriched = await attach_pull_request_comments(
                rest_client,
                [pull_request],
                organization="test-org",
            )

        assert mock_request.call_count == 3
        assert "__comments" in enriched[0]
        assert len(enriched[0]["__comments"]) == 4


def test_normalize_pull_request_comment_keeps_raw_review_fields() -> None:
    normalized = normalize_pull_request_comment(
        REVIEW,
        repo_name="repo1",
        pull_request_number=7,
        comment_type="review-summary",
    )
    assert normalized["__commentId"] == "repo1/7/review-summary/33"
    assert normalized["__commentType"] == "review-summary"
    assert normalized["submitted_at"] == "2026-10-01T02:00:00Z"
    assert "created_at" not in normalized
    assert "updated_at" not in normalized
    assert normalized["html_url"].endswith("#pullrequestreview-33")
    assert normalized["user"]["login"] == "reviewer"
    assert "__createdAt" not in normalized
    assert "__updatedAt" not in normalized
    assert "__url" not in normalized
    assert "__body" not in normalized
    assert "__author" not in normalized
