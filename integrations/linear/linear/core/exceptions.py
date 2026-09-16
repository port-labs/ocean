import json
from typing import Any

import httpx


class LinearApiError(Exception):
    """Raised when the Linear API returns an HTTP or GraphQL transport error."""

    @classmethod
    def from_response(cls, response: httpx.Response) -> "LinearApiError":
        return cls(cls._response_detail(response))

    @classmethod
    def from_graphql_errors(cls, errors: list[dict[str, Any]]) -> "LinearApiError":
        messages = [
            error.get("message", json.dumps(error)) for error in errors if error
        ]
        detail = "; ".join(messages) if messages else "Unknown GraphQL error"
        return cls(detail)

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            if graphql_errors := body.get("errors"):
                if isinstance(graphql_errors, list) and graphql_errors:
                    first_error = graphql_errors[0]
                    if isinstance(first_error, dict) and first_error.get("message"):
                        return str(first_error["message"])
            for key in ("error_description", "message", "error"):
                if (value := body.get(key)) is not None:
                    return value if isinstance(value, str) else json.dumps(value)

        text = response.text.strip()
        return text or f"HTTP {response.status_code}"
