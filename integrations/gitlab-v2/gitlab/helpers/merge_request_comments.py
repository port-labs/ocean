from typing import Any


def normalize_merge_request_note(
    note: dict[str, Any], merge_request: dict[str, Any]
) -> dict[str, Any]:
    """Attach the fields shared by the comment blueprint across integrations."""
    author_raw = note.get("author")
    author: dict[str, Any] = author_raw if isinstance(author_raw, dict) else {}
    body = note.get("body")
    if body is None:
        body = note.get("note") or ""
    comment_type = "review" if note.get("type") == "DiffNote" else "comment"
    merge_request_id = merge_request["id"]
    note_id = note["id"]
    web_url = str(merge_request.get("web_url") or "")
    url = str(note.get("url") or "")
    if not url and web_url:
        url = f"{web_url}#note_{note_id}"
    return {
        **note,
        "body": body,
        "__mergeRequestId": merge_request_id,
        "__commentId": f"{merge_request_id}/{note_id}",
        "__body": str(body),
        "__author": author.get("username") or author.get("name") or "",
        "__createdAt": note.get("created_at"),
        "__updatedAt": note.get("updated_at") or note.get("created_at"),
        "__url": url,
        "__commentType": comment_type,
    }


def is_human_merge_request_note(
    note: dict[str, Any], include_system_notes: bool
) -> bool:
    if note.get("system") and not include_system_notes:
        return False
    body = note.get("body")
    if body is None:
        body = note.get("note") or ""
    return bool(str(body).strip())
