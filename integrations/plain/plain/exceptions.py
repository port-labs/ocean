from typing import Any


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


def _format_graphql_errors(errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        messages.append(str(error.get("message") or "Unknown GraphQL error"))
    return "; ".join(messages) if messages else "Unknown GraphQL error"
