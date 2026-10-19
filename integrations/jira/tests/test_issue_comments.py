from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira.client import JiraClient
from jira.comments import (
    adf_to_plain_text,
    attach_comments_to_issues,
    issue_updated_within_days,
    normalize_issue_comment,
)
from jira.overrides import JiraIssueConfig, JiraIssueSelector
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
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


def _recent_updated() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%S.000+0000"
    )


def _old_updated(days: int = 60) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S.000+0000"
    )


def _issue_config(
    *, include_comments: bool = False, max_age_days: int = 30
) -> JiraIssueConfig:
    return JiraIssueConfig(
        kind="issue",
        selector=JiraIssueSelector(
            query="true",
            includeComments=include_comments,
            commentsMaxAgeDays=max_age_days,
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".key",
                    title=".fields.summary",
                    blueprint='"jiraIssue"',
                    properties={},
                )
            )
        ),
    )


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


@pytest.fixture
def comment_processor() -> IssueCommentWebhookProcessor:
    return IssueCommentWebhookProcessor(event=MagicMock())


def test_adf_to_plain_text_flattens_paragraphs() -> None:
    assert adf_to_plain_text(ADF_BODY) == "Please confirm the rollout window.\n"
    assert adf_to_plain_text("already plain") == "already plain"
    assert adf_to_plain_text(None) == ""


def test_normalize_issue_comment_sets_shared_fields() -> None:
    normalized = normalize_issue_comment(COMMENT, "TEST-1")
    assert normalized["__commentId"] == "TEST-1/10000"
    assert normalized["__body"] == "Please confirm the rollout window."
    assert (
        normalized["__url"]
        == "https://example.atlassian.net/browse/TEST-1?focusedCommentId=10000"
    )
    assert normalized["id"] == "10000"
    assert normalized["body"] == ADF_BODY
    assert normalized["author"] == COMMENT["author"]
    assert normalized["created"] == COMMENT["created"]
    assert normalized["updated"] == COMMENT["updated"]
    assert "__issueKey" not in normalized
    assert "__author" not in normalized
    assert "__createdAt" not in normalized
    assert "__updatedAt" not in normalized
    assert "__commentType" not in normalized


def test_issue_selector_include_comments_defaults_false() -> None:
    selector = JiraIssueSelector(query="true")
    assert selector.include_comments is False
    assert selector.comments_max_age_days == 30


def test_issue_updated_within_days_skips_missing_or_unparseable() -> None:
    assert issue_updated_within_days({"key": "TEST-1"}, 30) is False
    assert (
        issue_updated_within_days(
            {"key": "TEST-1", "fields": {"updated": "not-a-date"}}, 30
        )
        is False
    )


@pytest.mark.asyncio
async def test_flag_false_makes_no_comments_api_call(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    """includeComments defaults off: webhook must not call the comments API."""
    payload = {
        "webhookEvent": "comment_created",
        "comment": COMMENT,
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "fields": {"updated": _recent_updated()},
        },
    }
    # Default selector: includeComments=false
    config = _issue_config()

    with patch(
        "webhook_processors.issue_comment_webhook_processor.get_or_create_jira_client"
    ) as mock_get_client:
        result = await comment_processor.handle_event(payload, config)

    mock_get_client.assert_not_called()
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    assert config.selector.include_comments is False


@pytest.mark.asyncio
async def test_missing_updated_skips_comments_api_before_fetch(
    jira_client: JiraClient,
) -> None:
    issues = [{"key": "TEST-1", "fields": {"summary": "No updated"}}]
    with patch.object(jira_client, "get_paginated_comments_for_issue") as mock_comments:
        await attach_comments_to_issues(jira_client, issues, max_age_days=30)

    mock_comments.assert_not_called()
    assert "__comments" not in issues[0]


@pytest.mark.asyncio
async def test_recent_issue_attaches_all_comments_with_adf_flattened(
    jira_client: JiraClient,
) -> None:
    issues: list[dict[str, Any]] = [
        {
            "key": "TEST-1",
            "fields": {"updated": _recent_updated(), "summary": "Recent"},
        }
    ]

    async def _comment_pages(
        _issue_key: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [
            normalize_issue_comment(COMMENT, "TEST-1"),
            normalize_issue_comment({**COMMENT, "id": "10001"}, "TEST-1"),
        ]

    with patch.object(
        jira_client, "get_paginated_comments_for_issue", side_effect=_comment_pages
    ) as mock_comments:
        await attach_comments_to_issues(jira_client, issues, max_age_days=30)

    mock_comments.assert_called_once_with("TEST-1")
    comments = issues[0]["__comments"]
    assert len(comments) == 2
    assert comments[0]["__body"] == "Please confirm the rollout window."
    assert comments[0]["body"] == ADF_BODY
    assert comments[1]["__commentId"] == "TEST-1/10001"


@pytest.mark.asyncio
async def test_older_than_max_age_makes_no_comments_api_call(
    jira_client: JiraClient,
) -> None:
    issues = [
        {
            "key": "TEST-OLD",
            "fields": {"updated": _old_updated(60), "summary": "Old"},
        }
    ]
    with patch.object(jira_client, "get_paginated_comments_for_issue") as mock_comments:
        await attach_comments_to_issues(jira_client, issues, max_age_days=30)

    mock_comments.assert_not_called()
    assert "__comments" not in issues[0]


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


@pytest.mark.asyncio
async def test_comment_webhook_returns_issue_kind_with_comments_when_enabled(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    recent = _recent_updated()
    payload = {
        "webhookEvent": "comment_created",
        "comment": COMMENT,
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "fields": {"updated": recent, "summary": "Recent"},
        },
    }
    config = _issue_config(include_comments=True)

    async def _comment_pages(
        _issue_key: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [normalize_issue_comment(COMMENT, "TEST-1")]

    assert await comment_processor.should_process_event(MagicMock(payload=payload))
    assert await comment_processor.get_matching_kinds(MagicMock()) == [Kinds.ISSUE]

    with patch(
        "webhook_processors.issue_comment_webhook_processor.get_or_create_jira_client"
    ) as mock_get_client:
        client = MagicMock()
        client.get_paginated_comments_for_issue = MagicMock(side_effect=_comment_pages)
        mock_get_client.return_value = client
        result = await comment_processor.handle_event(payload, config)

    assert len(result.updated_raw_results) == 1
    updated = result.updated_raw_results[0]
    assert updated["key"] == "TEST-1"
    comments = updated["__comments"]
    assert comments[0]["__commentId"] == "TEST-1/10000"
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_comment_webhook_noop_when_include_comments_false(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    payload = {
        "webhookEvent": "comment_created",
        "comment": COMMENT,
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "fields": {"updated": _recent_updated()},
        },
    }
    config = _issue_config(include_comments=False)

    with patch(
        "webhook_processors.issue_comment_webhook_processor.get_or_create_jira_client"
    ) as mock_get_client:
        result = await comment_processor.handle_event(payload, config)

    mock_get_client.assert_not_called()
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_comment_webhook_deleted_still_returns_issue_with_refreshed_comments(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    payload = {
        "webhookEvent": "comment_deleted",
        "comment": {"id": "10000"},
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "fields": {"updated": _recent_updated()},
        },
    }
    config = _issue_config(include_comments=True)

    async def _comment_pages(
        _issue_key: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield []  # deleted comment absent from refreshed list

    with patch(
        "webhook_processors.issue_comment_webhook_processor.get_or_create_jira_client"
    ) as mock_get_client:
        client = MagicMock()
        client.get_paginated_comments_for_issue = MagicMock(side_effect=_comment_pages)
        mock_get_client.return_value = client
        result = await comment_processor.handle_event(payload, config)

    assert result.deleted_raw_results == []
    assert result.updated_raw_results[0]["__comments"] == []


@pytest.mark.asyncio
async def test_comment_webhook_outside_age_window_returns_empty(
    comment_processor: IssueCommentWebhookProcessor,
) -> None:
    payload = {
        "webhookEvent": "comment_updated",
        "comment": COMMENT,
        "issue": {
            "id": "10001",
            "key": "TEST-1",
            "fields": {"updated": _old_updated(90)},
        },
    }
    config = _issue_config(include_comments=True, max_age_days=30)

    with patch(
        "webhook_processors.issue_comment_webhook_processor.get_or_create_jira_client"
    ) as mock_get_client:
        client = MagicMock()
        client.get_paginated_comments_for_issue = MagicMock()
        mock_get_client.return_value = client
        result = await comment_processor.handle_event(payload, config)

    client.get_paginated_comments_for_issue.assert_not_called()
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


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
