from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from github.core.exporters.pull_request_exporter.utils import (
    attach_review_and_checks_if_requested,
    derive_review_decision_from_reviews,
    enrich_pull_request_review_and_checks,
    flatten_graphql_review_and_checks,
)


@pytest.mark.parametrize(
    ("reviews", "expected"),
    [
        ([], None),
        (
            [
                {
                    "user": {"login": "alice"},
                    "state": "APPROVED",
                    "submitted_at": "2024-01-01T00:00:00Z",
                }
            ],
            "approved",
        ),
        (
            [
                {
                    "user": {"login": "alice"},
                    "state": "APPROVED",
                    "submitted_at": "2024-01-01T00:00:00Z",
                },
                {
                    "user": {"login": "bob"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2024-01-02T00:00:00Z",
                },
            ],
            "changes_requested",
        ),
        (
            [
                {
                    "user": {"login": "alice"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2024-01-01T00:00:00Z",
                },
                {
                    "user": {"login": "alice"},
                    "state": "APPROVED",
                    "submitted_at": "2024-01-02T00:00:00Z",
                },
            ],
            "approved",
        ),
        (
            [
                {
                    "user": {"login": "alice"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2024-01-01T00:00:00Z",
                },
                {
                    "user": {"login": "alice"},
                    "state": "DISMISSED",
                    "submitted_at": "2024-01-02T00:00:00Z",
                },
            ],
            None,
        ),
        (
            [
                {
                    "user": {"login": "alice"},
                    "state": "COMMENTED",
                    "submitted_at": "2024-01-01T00:00:00Z",
                }
            ],
            None,
        ),
    ],
)
def test_derive_review_decision_from_reviews(
    reviews: list[dict[str, Any]], expected: Optional[str]
) -> None:
    assert derive_review_decision_from_reviews(reviews) == expected


def test_flatten_graphql_review_and_checks() -> None:
    pr_node: dict[str, Any] = {
        "reviewDecision": "CHANGES_REQUESTED",
        "statusCheckRollup": {"state": "FAILURE"},
    }
    flatten_graphql_review_and_checks(pr_node)
    assert pr_node["review_decision"] == "changes_requested"
    assert pr_node["checks_status"] == "failure"


def test_flatten_graphql_review_and_checks_handles_nulls() -> None:
    pr_node: dict[str, Any] = {
        "reviewDecision": None,
        "statusCheckRollup": None,
    }
    flatten_graphql_review_and_checks(pr_node)
    assert pr_node["review_decision"] is None
    assert pr_node["checks_status"] is None


@pytest.mark.asyncio
async def test_enrich_pull_request_review_and_checks() -> None:
    async def reviews_pages(
        *_args: Any, **_kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [
            {
                "user": {"login": "alice"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2024-01-01T00:00:00Z",
            }
        ]

    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock(return_value={"state": "failure"})
    client.send_paginated_request = MagicMock(side_effect=reviews_pages)

    pr = {
        "number": 12,
        "head": {"sha": "abc123"},
    }
    enriched = await enrich_pull_request_review_and_checks(client, "org", "repo", pr)

    assert enriched["checks_status"] == "failure"
    assert enriched["review_decision"] == "changes_requested"
    client.send_api_request.assert_awaited_once_with(
        "https://api.github.com/repos/org/repo/commits/abc123/status"
    )


@pytest.mark.asyncio
async def test_attach_review_and_checks_if_requested_noop_when_disabled() -> None:
    client = MagicMock()
    prs = [{"number": 1}]
    result = await attach_review_and_checks_if_requested(
        client,
        prs,
        organization="org",
        repo_name="repo",
        include_review_and_check_status=False,
    )
    assert result == prs
    client.send_api_request.assert_not_called()
