import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

_BLOCK_NODE_TYPES = {
    "paragraph",
    "heading",
    "listItem",
    "blockquote",
    "codeBlock",
    "bulletList",
    "orderedList",
}


class _CommentsClient(Protocol):
    def get_paginated_comments_for_issue(
        self, issue_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...


def adf_to_plain_text(body: Any) -> str:
    """Flatten a Jira ADF document, wiki string, or missing body into text."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        return "".join(adf_to_plain_text(item) for item in body)
    if not isinstance(body, dict):
        return ""
    if body.get("type") == "text":
        return str(body.get("text") or "")
    text = "".join(adf_to_plain_text(child) for child in body.get("content") or [])
    if body.get("type") in _BLOCK_NODE_TYPES and text and not text.endswith("\n"):
        return text + "\n"
    return text


def normalize_issue_comment(comment: dict[str, Any], issue_key: str) -> dict[str, Any]:
    """Attach the fields shared by the comment blueprint across integrations."""
    author_raw = comment.get("author")
    author: dict[str, Any] = author_raw if isinstance(author_raw, dict) else {}
    comment_id = str(comment.get("id") or "")
    self_url = str(comment.get("self") or "")
    host = ""
    if self_url.startswith("http"):
        parts = self_url.split("/")
        if len(parts) >= 3:
            host = "/".join(parts[:3])
    url = (
        f"{host}/browse/{issue_key}?focusedCommentId={comment_id}"
        if host and comment_id
        else self_url
    )
    author_name = (
        author.get("emailAddress")
        or author.get("displayName")
        or author.get("accountId")
        or ""
    )
    return {
        **comment,
        "__issueKey": issue_key,
        "__commentId": f"{issue_key}/{comment_id}",
        "__body": adf_to_plain_text(comment.get("body")).strip(),
        "__author": author_name,
        "__createdAt": comment.get("created"),
        "__updatedAt": comment.get("updated"),
        "__url": url,
        "__commentType": "comment",
    }


def parse_jira_datetime(value: str) -> datetime | None:
    """Parse a Jira datetime string; return None when unparseable."""
    normalized = value.replace("Z", "+00:00")
    # Jira often emits offsets like +0000 instead of +00:00
    if len(normalized) >= 5 and normalized[-5] in "+-" and normalized[-3] != ":":
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def issue_has_updated_field(issue: dict[str, Any]) -> bool:
    fields = issue.get("fields")
    return isinstance(fields, dict) and isinstance(fields.get("updated"), str)


def issue_updated_within_days(issue: dict[str, Any], max_age_days: int) -> bool:
    """Return True only when fields.updated parses and is within the window."""
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        return False
    updated = fields.get("updated")
    if not isinstance(updated, str):
        return False
    parsed = parse_jira_datetime(updated)
    if parsed is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return parsed >= cutoff


async def fetch_all_comments_for_issue(
    client: _CommentsClient, issue_key: str
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    async for batch in client.get_paginated_comments_for_issue(issue_key):
        comments.extend(batch)
    return comments


async def attach_comments_to_issues(
    client: _CommentsClient,
    issues: list[dict[str, Any]],
    max_age_days: int,
) -> list[dict[str, Any]]:
    """Attach `__comments` on issues that pass the age gate. Mutates and returns issues."""
    qualifying = [
        issue
        for issue in issues
        if issue.get("key") and issue_updated_within_days(issue, max_age_days)
    ]
    if not qualifying:
        return issues

    comment_lists = await asyncio.gather(
        *[
            fetch_all_comments_for_issue(client, str(issue["key"]))
            for issue in qualifying
        ]
    )
    for issue, comments in zip(qualifying, comment_lists):
        issue["__comments"] = comments
    return issues
