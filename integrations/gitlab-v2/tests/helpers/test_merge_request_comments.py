from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.merge_request_comments import (
    is_human_merge_request_note,
    normalize_merge_request_note,
)
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors.merge_request_comment_webhook_processor import (
    MergeRequestCommentWebhookProcessor,
)
from integration import (
    GitlabMergeRequestResourceConfig,
    GitlabMergeRequestSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)

NOW = datetime.now(timezone.utc)

MERGE_REQUEST = {
    "id": 99,
    "iid": 1,
    "project_id": 5,
    "state": "opened",
    "updated_at": NOW.isoformat().replace("+00:00", "Z"),
    "web_url": "https://gitlab.example.com/group/project/-/merge_requests/1",
}

OLD_MERGE_REQUEST = {
    **MERGE_REQUEST,
    "updated_at": (NOW - timedelta(days=45)).isoformat().replace("+00:00", "Z"),
}

NOTE = {
    "id": 302,
    "body": "Please split this change.",
    "author": {"username": "reviewer"},
    "created_at": "2026-10-01T00:00:00.000Z",
    "updated_at": "2026-10-01T01:00:00.000Z",
    "system": False,
    "type": None,
}

DIFF_NOTE = {
    **NOTE,
    "id": 303,
    "type": "DiffNote",
    "body": "Rename this variable.",
}

SYSTEM_NOTE = {**NOTE, "id": 304, "system": True, "body": "changed the description"}


def test_normalize_discussion_and_diff_notes() -> None:
    discussion = normalize_merge_request_note(NOTE, MERGE_REQUEST)
    review = normalize_merge_request_note(DIFF_NOTE, MERGE_REQUEST)
    assert discussion["__commentId"] == "99/302"
    assert discussion["__commentType"] == "comment"
    assert discussion["body"] == "Please split this change."
    assert discussion["author"]["username"] == "reviewer"
    assert discussion["created_at"] == "2026-10-01T00:00:00.000Z"
    assert discussion["__url"].endswith("#note_302")
    assert "url" not in discussion
    assert "__body" not in discussion
    assert "__author" not in discussion
    assert "__createdAt" not in discussion
    assert "__updatedAt" not in discussion
    assert "__mergeRequestId" not in discussion
    assert review["__commentType"] == "review"
    assert review["body"] == "Rename this variable."


def test_normalize_uses_webhook_note_field() -> None:
    webhook_note = {
        "id": 305,
        "note": "From webhook payload",
        "author": {"name": "alice"},
        "created_at": "2026-10-01T00:00:00.000Z",
        "system": False,
        "type": None,
        "url": "https://gitlab.example.com/group/project/-/merge_requests/1#note_305",
    }
    normalized = normalize_merge_request_note(webhook_note, MERGE_REQUEST)
    assert normalized["body"] == "From webhook payload"
    assert normalized["author"]["name"] == "alice"
    assert normalized["url"].endswith("#note_305")
    assert "__url" not in normalized
    assert "__body" not in normalized
    assert "__author" not in normalized


def test_system_notes_are_skipped() -> None:
    assert is_human_merge_request_note(SYSTEM_NOTE) is False
    assert is_human_merge_request_note(SYSTEM_NOTE, True) is True
    assert is_human_merge_request_note({**NOTE, "body": "  "}) is False


@pytest.mark.asyncio
async def test_attaches_human_notes_and_skips_system() -> None:
    client = GitLabClient.__new__(GitLabClient)
    client.get_merge_request_notes = AsyncMock(  # type: ignore[method-assign]
        return_value=[NOTE, DIFF_NOTE, SYSTEM_NOTE]
    )
    result = await client.attach_merge_request_comments(
        [MERGE_REQUEST.copy()],
        max_concurrent=1,
    )
    comments = result[0]["__comments"]
    assert [comment["__commentId"] for comment in comments] == ["99/302", "99/303"]
    assert comments[0]["__commentType"] == "comment"
    assert comments[1]["__commentType"] == "review"
    client.get_merge_request_notes.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "merge_request",
    [
        OLD_MERGE_REQUEST,
        {**MERGE_REQUEST, "updated_at": None},
        {k: v for k, v in MERGE_REQUEST.items() if k != "updated_at"},
        {**MERGE_REQUEST, "updated_at": "not-a-date"},
    ],
)
async def test_comments_load_for_old_missing_or_unparseable_updated_at(
    merge_request: dict[str, Any],
) -> None:
    client = GitLabClient.__new__(GitLabClient)
    client.get_merge_request_notes = AsyncMock(  # type: ignore[method-assign]
        return_value=[NOTE]
    )
    result = await client.attach_merge_request_comments(
        [merge_request.copy()],
        max_concurrent=1,
    )
    assert result[0]["__comments"][0]["__commentId"] == "99/302"
    client.get_merge_request_notes.assert_awaited_once()


def _processor() -> MergeRequestCommentWebhookProcessor:
    return MergeRequestCommentWebhookProcessor(event=MagicMock())


def _config(*, include_comments: bool = True) -> GitlabMergeRequestResourceConfig:
    return GitlabMergeRequestResourceConfig(
        kind="merge-request",
        selector=GitlabMergeRequestSelector.parse_obj(
            {
                "query": "true",
                "states": ["opened"],
                "includeComments": include_comments,
            }
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id | tostring",
                    title=".title",
                    blueprint='"gitlabMergeRequest"',
                    properties={},
                )
            )
        ),
    )


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "object_kind": "note",
        "object_attributes": {
            "id": 302,
            "note": "Please split this change.",
            "noteable_type": "MergeRequest",
            "created_at": "2026-10-01T00:00:00.000Z",
            "updated_at": "2026-10-01T00:00:00.000Z",
            "system": False,
            "type": None,
            "url": "https://gitlab.example.com/group/project/-/merge_requests/1#note_302",
        },
        "merge_request": MERGE_REQUEST.copy(),
        "user": {"username": "reviewer"},
        "project": {"id": 5},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_webhook_returns_merge_request_kind_with_comments() -> None:
    processor = _processor()
    event = MagicMock()
    event.headers = {"x-gitlab-event": "Note Hook"}
    event.payload = _payload()
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == [ObjectKind.MERGE_REQUEST]

    fetched_mr = MERGE_REQUEST.copy()
    processor._gitlab_webhook_client = MagicMock()
    processor._gitlab_webhook_client.get_merge_request = AsyncMock(
        return_value=fetched_mr
    )
    processor._gitlab_webhook_client.enrich_merge_requests = AsyncMock()
    processor._gitlab_webhook_client.attach_merge_request_comments = AsyncMock(
        return_value=[{**fetched_mr, "__comments": [{"__commentId": "99/302"}]}]
    )

    result = await processor.handle_event(_payload(), _config(include_comments=True))
    assert result.updated_raw_results[0]["__comments"][0]["__commentId"] == "99/302"
    assert result.deleted_raw_results == []
    processor._gitlab_webhook_client.get_merge_request.assert_awaited_once()
    processor._gitlab_webhook_client.attach_merge_request_comments.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_noops_when_include_comments_false() -> None:
    processor = _processor()
    processor._gitlab_webhook_client = MagicMock()
    processor._gitlab_webhook_client.get_merge_request = AsyncMock()
    processor._gitlab_webhook_client.attach_merge_request_comments = AsyncMock()

    result = await processor.handle_event(_payload(), _config(include_comments=False))
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    processor._gitlab_webhook_client.get_merge_request.assert_not_called()
    processor._gitlab_webhook_client.attach_merge_request_comments.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_ignores_issue_notes() -> None:
    processor = _processor()
    issue_event = MagicMock()
    issue_event.headers = {"x-gitlab-event": "Note Hook"}
    issue_event.payload = _payload()
    issue_event.payload["object_attributes"]["noteable_type"] = "Issue"
    assert await processor.should_process_event(issue_event) is False
