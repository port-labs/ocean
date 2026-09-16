import json
from typing import Any

import httpx


class LinearApiError(Exception):
    """Raised when the Linear API returns an HTTP or GraphQL transport error."""

    @classmethod
    def from_response(cls, response: httpx.Response) -> "LinearApiError":
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            graphql_errors = body.get("errors")
            if isinstance(graphql_errors, list) and graphql_errors:
                return cls.from_graphql_errors(graphql_errors)

        return cls(cls._response_detail(response))

    @classmethod
    def from_graphql_errors(cls, errors: list[dict[str, Any]]) -> "LinearApiError":
        details = [
            cls._format_graphql_error(error)
            for error in errors
            if isinstance(error, dict)
        ]
        return cls("; ".join(details) if details else "Unknown GraphQL error")

    @staticmethod
    def _format_graphql_error(error: dict[str, Any]) -> str:
        extensions = error.get("extensions")
        if isinstance(extensions, dict):
            if user_message := extensions.get("userPresentableMessage"):
                return str(user_message)

            exception = extensions.get("exception")
            if isinstance(exception, dict):
                validation_errors = exception.get("validationErrors")
                if isinstance(validation_errors, list):
                    field_errors: list[str] = []
                    for validation_error in validation_errors:
                        if not isinstance(validation_error, dict):
                            continue
                        if formatted := LinearApiError._format_validation_error(
                            validation_error
                        ):
                            field_errors.append(formatted)
                    if field_errors:
                        return "; ".join(field_errors)

        message = str(error.get("message", "Unknown GraphQL error"))
        path = error.get("path")
        if isinstance(path, list) and path:
            return f"{message} ({path[-1]})"
        return message

    @staticmethod
    def _format_validation_error(validation_error: dict[str, Any]) -> str | None:
        field = validation_error.get("property")
        constraints = validation_error.get("constraints")
        if not isinstance(constraints, dict) or not constraints:
            return str(field) if field else None

        constraint_message = next(iter(constraints.values()))
        if field:
            return f"{field}: {constraint_message}"
        return str(constraint_message)

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            for key in ("error_description", "message", "error"):
                if (value := body.get(key)) is not None:
                    return value if isinstance(value, str) else json.dumps(value)

        text = response.text.strip()
        return text or f"HTTP {response.status_code}"
