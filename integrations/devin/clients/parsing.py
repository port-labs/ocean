from typing import Any

from loguru import logger
from pydantic import ValidationError

from clients.models import SessionMessage, SessionResponse


def _sanitize_session_dict(data: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(data)
    if prepared.get("tags") is None:
        prepared["tags"] = []
    pull_requests = prepared.get("pull_requests")
    if isinstance(pull_requests, list):
        prepared["pull_requests"] = [
            entry
            for entry in pull_requests
            if isinstance(entry, dict)
            and isinstance(entry.get("pr_url"), str)
            and entry["pr_url"]
        ]
    return prepared


def _session_label(data: dict[str, Any]) -> str:
    session_id = data.get("session_id")
    return str(session_id) if session_id else "unknown"


def require_session_response(data: Any) -> SessionResponse:
    """Strict parse for user-initiated session operations."""
    if not isinstance(data, dict):
        raise TypeError(
            f"Devin session payload must be a dict, got {type(data).__name__}"
        )
    return SessionResponse.model_validate(_sanitize_session_dict(data))


def parse_session_response_best_effort(data: Any) -> SessionResponse | None:
    """Parse one session from a list response; skip and log on unrecoverable input."""
    if not isinstance(data, dict):
        logger.warning(
            f"Skipping Devin session list item: expected dict, got {type(data).__name__}"
        )
        return None

    prepared = _sanitize_session_dict(data)
    prepared.setdefault("url", "")
    if "created_at" not in prepared and "updated_at" in prepared:
        prepared["created_at"] = prepared["updated_at"]
    elif "updated_at" not in prepared and "created_at" in prepared:
        prepared["updated_at"] = prepared["created_at"]
    elif "created_at" not in prepared:
        prepared["created_at"] = 0
    if "updated_at" not in prepared:
        prepared["updated_at"] = prepared.get("created_at", 0)

    try:
        return SessionResponse.model_validate(prepared)
    except ValidationError as error:
        logger.warning(
            f"Skipping Devin session {_session_label(prepared)} from list: {error}"
        )
        return None


def parse_session_message_best_effort(data: Any) -> SessionMessage | None:
    if not isinstance(data, dict):
        logger.warning(
            f"Skipping Devin session message: expected dict, got {type(data).__name__}"
        )
        return None
    try:
        return SessionMessage.model_validate(data)
    except ValidationError as error:
        event_id = data.get("event_id", "unknown")
        logger.warning(f"Skipping Devin session message {event_id}: {error}")
        return None
