import json
from typing import Any

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""

    DEFAULT_STATUS_LABEL = "Invalid inputs"


class LinearActionError(ActionExecutionError):
    """Raised when the Linear API returns an error while executing an action."""

    DEFAULT_STATUS_LABEL = "Linear failed"

    @classmethod
    def from_response(cls, response: httpx.Response) -> "LinearActionError":
        return cls(cls._response_detail(response))

    @classmethod
    def from_graphql_errors(cls, errors: list[dict[str, Any]]) -> "LinearActionError":
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


class CreateIssueError(LinearActionError):
    """Raised when creating a Linear issue fails."""

    DEFAULT_STATUS_LABEL = "Create failed"


class UpdateIssueError(LinearActionError):
    """Raised when updating a Linear issue fails."""

    DEFAULT_STATUS_LABEL = "Update failed"
