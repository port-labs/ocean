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


class _CommentsPaginationClient(Protocol):
    api_url: str

    def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...


def _attr_node_text(node_type: str, attrs: dict[str, Any]) -> str:
    """Visible text for ADF inline nodes that store their value in attrs."""
    if node_type == "mention":
        return str(attrs.get("text") or attrs.get("id") or "")
    if node_type == "emoji":
        return str(attrs.get("shortName") or attrs.get("text") or "")
    if node_type == "date":
        timestamp = attrs.get("timestamp")
        return str(timestamp) if timestamp is not None else ""
    if node_type in {"inlineCard", "blockCard", "embedCard"}:
        return str(attrs.get("url") or "")
    if node_type == "status":
        return str(attrs.get("text") or "")
    return ""


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
    node_type = body.get("type")
    if node_type == "text":
        return str(body.get("text") or "")
    if node_type == "hardBreak":
        return "\n"
    attrs = body.get("attrs")
    if isinstance(attrs, dict) and node_type:
        attr_text = _attr_node_text(str(node_type), attrs)
        if attr_text:
            return attr_text
    text = "".join(adf_to_plain_text(child) for child in body.get("content") or [])
    if node_type in _BLOCK_NODE_TYPES and text and not text.endswith("\n"):
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


# Match the Jira HTTP client cap so a large issue batch cannot open one
# comment fetch per issue at the same time.
_MAX_CONCURRENT_COMMENT_FETCHES = 10


async def fetch_all_comments_for_issue(
    client: _CommentsPaginationClient, issue_key: str
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    url = f"{client.api_url}/issue/{issue_key}/comment"
    async for batch in client._get_paginated_data(url, "comments"):
        comments.extend(
            normalize_issue_comment(comment, issue_key) for comment in batch
        )
    return comments


async def attach_comments_to_issues(
    client: _CommentsPaginationClient,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach `__comments` on every issue that has a key. Mutates and returns issues."""
    with_keys = [issue for issue in issues if issue.get("key")]
    if not with_keys:
        return issues

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_COMMENT_FETCHES)

    async def _fetch_one(issue_key: str) -> list[dict[str, Any]]:
        async with semaphore:
            return await fetch_all_comments_for_issue(client, issue_key)

    comment_lists = await asyncio.gather(
        *[_fetch_one(str(issue["key"])) for issue in with_keys]
    )
    for issue, comments in zip(with_keys, comment_lists):
        issue["__comments"] = comments
    return issues
