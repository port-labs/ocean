import json
from typing import Self

import httpx

from port_ocean.exceptions.execution_manager import ActionExecutionError


class AzureDevopsActionError(ActionExecutionError):
    """Base class for failures raised while executing an Azure DevOps action.

    Subclassing ``ActionExecutionError`` makes the execution manager log the
    failure without a stack trace and report the message to Port verbatim, so
    whoever triggered the action sees what to fix.
    """

    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        return cls(f"{prefix}: {cls._response_detail(response)}")

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            message = body.get("message")
            if message is not None:
                return message if isinstance(message, str) else json.dumps(message)

        text = response.text.strip()
        return text or f"HTTP {response.status_code}"


class InvalidActionParametersError(AzureDevopsActionError):
    """Raised when an action run is missing required parameters."""

    DEFAULT_STATUS_LABEL = "Invalid input"


class MultipleOrganizationsNotSupportedError(AzureDevopsActionError):
    """Raised when actions are invoked while multiple organizations are configured."""

    DEFAULT_STATUS_LABEL = "Unsupported config"


class TriggerPipelineError(AzureDevopsActionError):
    """Raised when the Azure DevOps API returns an error while triggering a pipeline."""

    DEFAULT_STATUS_LABEL = "Trigger failed"


class UpdatePullRequestError(AzureDevopsActionError):
    """Raised when the Azure DevOps API returns an error while updating a pull request."""

    DEFAULT_STATUS_LABEL = "Update failed"
