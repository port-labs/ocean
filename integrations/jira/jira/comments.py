from typing import Any

_BLOCK_NODE_TYPES = {
    "paragraph",
    "heading",
    "listItem",
    "blockquote",
    "codeBlock",
    "bulletList",
    "orderedList",
}


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
