from typing import Any


def normalize_merge_request_note(
    note: dict[str, Any], merge_request: dict[str, Any]
) -> dict[str, Any]:
    """Normalize a GitLab note for itemsToParse under merge-request.__comments.

    Keeps raw GitLab note fields and adds only real transforms: ``__commentId``,
    ``__commentType``, and ``__url`` when the note has no ``url``. Webhook notes
    use ``note`` for the body; that is copied onto ``body`` when missing so
    mappings can always read ``.item.body``.
    """
    body = note.get("body")
    if body is None:
        body = note.get("note") or ""
    comment_type = "review" if note.get("type") == "DiffNote" else "comment"
    merge_request_id = merge_request["id"]
    note_id = note["id"]
    normalized: dict[str, Any] = {
        **note,
        "body": body,
        "__commentId": f"{merge_request_id}/{note_id}",
        "__commentType": comment_type,
    }
    if not note.get("url"):
        web_url = str(merge_request.get("web_url") or "")
        if web_url:
            normalized["__url"] = f"{web_url}#note_{note_id}"
    return normalized


def has_merge_request_note_body(note: dict[str, Any]) -> bool:
    """Return True when the note has non-empty body or note text."""
    body = note.get("body")
    if body is None:
        body = note.get("note") or ""
    return bool(str(body).strip())
