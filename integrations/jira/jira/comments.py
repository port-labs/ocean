import asyncio
from collections.abc import AsyncGenerator
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
    """Keep raw Jira comment fields and add only justified transforms.

    ``__commentId`` prefixes the issue key because comment ids are not unique
    across issues. ``__body`` flattens ADF (``body`` is not a string). ``__url``
    is the browse URL; Jira's payload only has the REST ``self`` link.
    """
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
    return {
        **comment,
        "__commentId": f"{issue_key}/{comment_id}",
        "__body": adf_to_plain_text(comment.get("body")).strip(),
        "__url": url,
    }


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
) -> list[dict[str, Any]]:
    """Attach `__comments` on every issue that has a key. Mutates and returns issues."""
    with_keys = [issue for issue in issues if issue.get("key")]
    if not with_keys:
        return issues

    comment_lists = await asyncio.gather(
        *[
            fetch_all_comments_for_issue(client, str(issue["key"]))
            for issue in with_keys
        ]
    )
    for issue, comments in zip(with_keys, comment_lists):
        issue["__comments"] = comments
    return issues
