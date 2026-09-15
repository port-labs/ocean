import json
from typing import Self

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""

    DEFAULT_STATUS_LABEL = "Invalid input"


class JiraActionError(ActionExecutionError):
    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
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

    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        return cls(f"{prefix}: {cls._response_detail(response)}")


class CreateIssueError(JiraActionError):
    """Raised when the Jira API returns an error while creating an issue."""

    DEFAULT_STATUS_LABEL = "Create failed"


class ChangeIssueStatusError(JiraActionError):
    """Raised when the Jira API returns an error while changing issue status."""

    DEFAULT_STATUS_LABEL = "Status change failed"
