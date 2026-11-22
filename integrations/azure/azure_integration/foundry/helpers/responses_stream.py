from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from azure_integration.foundry.models.responses import TERMINAL_EVENTS

# Re-export for stream_manager / tests.
TERMINAL_SSE_TYPES = TERMINAL_EVENTS

_RESPONSE_ID_EVENT_TYPES = {
    "response.created",
    "response.in_progress",
    "response.completed",
}


class ResponsesSseEvent(BaseModel):
    """SSE envelope. Nested ``response`` stays a dict — payload is large/variable."""

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
    return str(response["id"]) if response and response.get("id") else None


def format_responses_sse_log_message(parsed: ResponsesSseEvent) -> str | None:
    if parsed.type == "response.output_text.delta":
        return None
    if parsed.type == "response.output_text.done":
        return (
            parsed.text
            if isinstance(parsed.text, str) and parsed.text.strip()
            else None
        )
    if parsed.type == "error":
        message = parsed.message or parsed.error
        return f"Error: {message}" if message else None
    if parsed.response and isinstance(parsed.response.get("error"), dict):
        error = parsed.response["error"]
        msg = error.get("message") or error.get("code")
        return f"Error: {msg}" if msg else None
    return None
