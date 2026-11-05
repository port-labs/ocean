from __future__ import annotations

import json
from typing import Any

from azure_integration.foundry.helpers.webhook_scope import usage_from_response

_TERMINAL_SSE_TYPES = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}


def parse_responses_sse_payload(payload: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def response_id_from_sse_event(parsed: dict[str, Any]) -> str | None:
    event_type = parsed.get("type")
    if event_type not in {"response.created", "response.in_progress", "response.completed"}:
        return None
    response = parsed.get("response")
    if isinstance(response, dict) and response.get("id"):
        return str(response["id"])
    return None


def success_for_terminal_sse_event(event_type: str) -> bool | None:
    if event_type in _TERMINAL_SSE_TYPES:
        return _TERMINAL_SSE_TYPES[event_type]
    return None


def format_responses_sse_log_message(parsed: dict[str, Any]) -> str | None:
    """Human-readable Port run log line for a Responses SSE event, or None to skip."""
    event_type = parsed.get("type")
    if not isinstance(event_type, str):
        return None

    if event_type == "response.output_text.delta":
        return None

    if event_type == "response.output_text.done":
        text = parsed.get("text")
        if isinstance(text, str) and text.strip():
            return text
        return None

    if event_type == "response.completed":
        response = parsed.get("response")
        if isinstance(response, dict):
            usage = usage_from_response(response)
            if usage:
                parts = ", ".join(f"{key}={value}" for key, value in usage.items())
                return f"Response completed ({parts})"
        return "Response completed"

    if event_type == "error":
        message = parsed.get("message") or parsed.get("error")
        if message:
            return f"Error: {message}"

    response = parsed.get("response")
    if isinstance(response, dict) and response.get("error"):
        error = response["error"]
        if isinstance(error, dict):
            msg = error.get("message") or error.get("code")
            if msg:
                return f"Error: {msg}"

    return None
