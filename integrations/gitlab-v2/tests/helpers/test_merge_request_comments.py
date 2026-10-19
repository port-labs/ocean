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
    GitlabMergeRequestCommentResourceConfig,
    GitlabMergeRequestCommentSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)

MERGE_REQUEST = {
    "id": 99,
    "iid": 1,
    "project_id": 5,
    "state": "opened",
    "web_url": "https://gitlab.example.com/group/project/-/merge_requests/1",
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
    assert discussion["__author"] == "reviewer"
    assert discussion["__url"].endswith("#note_302")
    assert review["__commentType"] == "review"
    assert review["__mergeRequestId"] == 99


def test_system_notes_are_skipped_unless_requested() -> None:
    assert is_human_merge_request_note(SYSTEM_NOTE, False) is False
    assert is_human_merge_request_note(SYSTEM_NOTE, True) is True
    assert is_human_merge_request_note({**NOTE, "body": "  "}, False) is False


@pytest.mark.asyncio
async def test_client_returns_normalized_comments() -> None:
    client = GitLabClient.__new__(GitLabClient)
    client.get_merge_request_notes = AsyncMock(return_value=[NOTE, DIFF_NOTE, SYSTEM_NOTE])  # type: ignore[method-assign]
    comments = await client.get_merge_request_comments(MERGE_REQUEST)
    assert [comment["__commentId"] for comment in comments] == ["99/302", "99/303"]


def _processor() -> MergeRequestCommentWebhookProcessor:
    return MergeRequestCommentWebhookProcessor(event=MagicMock())


def _config() -> GitlabMergeRequestCommentResourceConfig:
    return GitlabMergeRequestCommentResourceConfig(
        kind="merge-request-comment",
        selector=GitlabMergeRequestCommentSelector(query="true", states=["opened"]),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".__commentId",
                    title=".__body",
                    blueprint='"gitlabMergeRequestComment"',
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
        "merge_request": MERGE_REQUEST,
        "user": {"username": "reviewer"},
        "project": {"id": 5},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_webhook_upserts_merge_request_note() -> None:
    processor = _processor()
    event = MagicMock()
    event.headers = {"x-gitlab-event": "Note Hook"}
    event.payload = _payload()
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == [
        ObjectKind.MERGE_REQUEST_COMMENT
    ]
    result = await processor.handle_event(_payload(), _config())
    assert result.updated_raw_results[0]["__commentId"] == "99/302"
    assert result.updated_raw_results[0]["__author"] == "reviewer"
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_webhook_ignores_issue_notes_and_system_notes() -> None:
    processor = _processor()
    issue_event = MagicMock()
    issue_event.headers = {"x-gitlab-event": "Note Hook"}
    issue_event.payload = _payload()
    issue_event.payload["object_attributes"]["noteable_type"] = "Issue"
    assert await processor.should_process_event(issue_event) is False

    system_payload = _payload()
    system_payload["object_attributes"]["system"] = True
    result = await processor.handle_event(system_payload, _config())
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []

    closed_payload = _payload()
    closed_payload["merge_request"] = {**MERGE_REQUEST, "state": "closed"}
    closed_result = await processor.handle_event(closed_payload, _config())
    assert closed_result.updated_raw_results == []
    assert closed_result.deleted_raw_results[0]["__commentId"] == "99/302"
