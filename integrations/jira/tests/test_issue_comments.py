from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira.client import JiraClient
from jira.comments import adf_to_plain_text, normalize_issue_comment
from kinds import Kinds
from webhook_processors.issue_comment_webhook_processor import (
    IssueCommentWebhookProcessor,
)

ADF_BODY = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Please confirm the rollout window."}],
        }
    ],
}

COMMENT = {
    "id": "10000",
    "self": "https://example.atlassian.net/rest/api/3/issue/10001/comment/10000",
    "body": ADF_BODY,
    "author": {
        "accountId": "712020:test-account-id",
        "displayName": "Test User",
        "emailAddress": "test.user@example.com",
    },
    "created": "2024-01-15T10:00:00.000+0000",
    "updated": "2024-01-15T11:00:00.000+0000",
}


def test_adf_to_plain_text_flattens_paragraphs() -> None:
    assert adf_to_plain_text(ADF_BODY) == "Please confirm the rollout window.\n"
    assert adf_to_plain_text("already plain") == "already plain"
    assert adf_to_plain_text(None) == ""


def test_normalize_issue_comment_sets_shared_fields() -> None:
    normalized = normalize_issue_comment(COMMENT, "TEST-1")
    assert normalized["__commentId"] == "TEST-1/10000"
    assert normalized["__issueKey"] == "TEST-1"
    assert normalized["__body"] == "Please confirm the rollout window."
    assert normalized["__author"] == "test.user@example.com"
    assert normalized["__commentType"] == "comment"
    assert (
        normalized["__url"]
        == "https://example.atlassian.net/browse/TEST-1?focusedCommentId=10000"
    )
    assert normalized["id"] == "10000"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.oauth_access_token_file_path = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def jira_client() -> JiraClient:
    return JiraClient(
        jira_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_token="test_token",
    )


@pytest.mark.asyncio
async def test_get_paginated_comments_for_issue(jira_client: JiraClient) -> None:
    with patch.object(
        jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
            "comments": [COMMENT],
        }
        comments: list[dict[str, Any]] = []
        async for batch in jira_client.get_paginated_comments_for_issue("TEST-1"):
            comments.extend(batch)

    assert comments[0]["__commentId"] == "TEST-1/10000"
    assert mock_request.await_args is not None
    assert mock_request.await_args.args[1].endswith("/issue/TEST-1/comment")


@pytest.fixture
def comment_processor() -> IssueCommentWebhookProcessor:
    return IssueCommentWebhookProcessor(event=MagicMock())


@pytest.mark.asyncio
async def test_comment_webhook_upserts_created_comment(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    payload = {
        "webhookEvent": "comment_created",
        "comment": COMMENT,
        "issue": {"id": "10001", "key": "TEST-1"},
    }
    assert await comment_processor.should_process_event(MagicMock(payload=payload))
    assert await comment_processor.get_matching_kinds(MagicMock()) == [
        Kinds.ISSUE_COMMENT
    ]
    result = await comment_processor.handle_event(payload, MagicMock())
    assert result.updated_raw_results[0]["__commentId"] == "TEST-1/10000"
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_comment_webhook_deletes_comment(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    payload = {
        "webhookEvent": "comment_deleted",
        "comment": {"id": "10000"},
        "issue": {"id": "10001", "key": "TEST-1"},
    }
    result = await comment_processor.handle_event(payload, MagicMock())
    assert result.updated_raw_results == []
    assert result.deleted_raw_results[0]["__commentId"] == "TEST-1/10000"


@pytest.mark.asyncio
async def test_comment_webhook_rejects_payload_without_issue_key(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    assert (
        await comment_processor.validate_payload(
            {"webhookEvent": "comment_created", "comment": COMMENT}
        )
        is False
    )
