import json
import re
from typing import Any

_MISSING_PERMISSION = re.compile(r'missing "([^"]+)"')


class PlainGraphQLError(Exception):
    """Raised when Plain returns a GraphQL ``errors`` array."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(_format_graphql_errors(errors))


class PlainHTTPError(Exception):
    """Raised when Plain returns a non-2xx response before GraphQL parsing."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        detail = body.strip() or "empty body"
        super().__init__(f"Plain API HTTP {status_code}: {detail}")


def missing_permission_names(payload: Any) -> list[str]:
    """Return permission names from Plain's insufficient-permission errors."""
    found: list[str] = []
    for message in _error_messages(payload):
        for name in _MISSING_PERMISSION.findall(message):
            if name not in found:
                found.append(name)
    return found


def _error_messages(payload: Any) -> list[str]:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except ValueError:
            return [payload]
        return _error_messages(parsed)
    if isinstance(payload, dict):
        messages: list[str] = []
        message = payload.get("message")
        if isinstance(message, str):
            messages.append(message)
        errors = payload.get("errors")
        if errors is not None:
            messages.extend(_error_messages(errors))
        return messages
    if isinstance(payload, list):
        collected: list[str] = []
        for item in payload:
            collected.extend(_error_messages(item))
        return collected
    return []


def _format_graphql_errors(errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        messages.append(str(error.get("message") or "Unknown GraphQL error"))
    return "; ".join(messages) if messages else "Unknown GraphQL error"
