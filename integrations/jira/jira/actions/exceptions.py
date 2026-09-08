import json

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""

    DEFAULT_STATUS_LABEL = "Invalid input"


def _jira_response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = None

    if isinstance(body, dict):
        error_messages = body.get("errorMessages")
        if isinstance(error_messages, list) and error_messages:
            return "; ".join(str(message) for message in error_messages)

        errors = body.get("errors")
        if isinstance(errors, dict) and errors:
            return "; ".join(f"{key}: {value}" for key, value in errors.items())

        for key in ("message", "error"):
            if (value := body.get(key)) is not None:
                return value if isinstance(value, str) else json.dumps(value)

    text = response.text.strip()
    return text or f"HTTP {response.status_code}"


class CreateIssueError(ActionExecutionError):
    """Raised when the Jira API returns an error while creating an issue."""

    DEFAULT_STATUS_LABEL = "Create failed"

    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> "CreateIssueError":
        return cls(f"{prefix}: {_jira_response_detail(response)}")


class ChangeIssueStatusError(ActionExecutionError):
    """Raised when the Jira API returns an error while changing issue status."""

    DEFAULT_STATUS_LABEL = "Status change failed"

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "ChangeIssueStatusError":
        return cls(f"{prefix}: {_jira_response_detail(response)}")
