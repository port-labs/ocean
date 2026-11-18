from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

_TERMINAL_SSE_TYPES = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}

_RESPONSE_ID_EVENT_TYPES = {
    "response.created",
    "response.in_progress",
    "response.completed",
}


class ResponsesSseEvent(BaseModel):
    """SSE event envelope. Nested ``response`` stays a dict — payload is large/variable."""

    model_config = ConfigDict(extra="ignore")

    type: str
    text: str | None = None
    message: str | None = None
    error: Any = None
    response: dict[str, Any] | None = None


def parse_responses_sse_payload(payload: str) -> ResponsesSseEvent | None:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return ResponsesSseEvent.model_validate(raw)
    except ValidationError:
        return None


def response_id_from_sse_event(parsed: ResponsesSseEvent) -> str | None:
    if parsed.type not in _RESPONSE_ID_EVENT_TYPES:
        return None
    response = parsed.response
    if response and response.get("id"):
        return str(response["id"])
    return None


def success_for_terminal_sse_event(event_type: str) -> bool | None:
    return _TERMINAL_SSE_TYPES.get(event_type)


def format_responses_sse_log_message(parsed: ResponsesSseEvent) -> str | None:
    """Human-readable Port run log line for a Responses SSE event, or None to skip."""
    if parsed.type == "response.output_text.delta":
        return None

    if parsed.type == "response.output_text.done":
        if isinstance(parsed.text, str) and parsed.text.strip():
            return parsed.text
        return None

    if parsed.type == "error":
        message = parsed.message or parsed.error
        if message:
            return f"Error: {message}"

    if parsed.response and isinstance(parsed.response.get("error"), dict):
        error = parsed.response["error"]
        msg = error.get("message") or error.get("code")
        if msg:
            return f"Error: {msg}"

    return None
