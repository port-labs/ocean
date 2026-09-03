import json

import httpx

from port_ocean.exceptions.execution_manager import ActionExecutionError


class InvalidActionParametersError(ActionExecutionError):
    """Raised when an action run is missing required parameters."""

    DEFAULT_STATUS_LABEL = "Invalid action inputs"


class MultipleOrganizationsNotSupportedError(ActionExecutionError):
    """Raised when actions are invoked while multiple organizations are configured."""

    DEFAULT_STATUS_LABEL = "Unsupported configuration"


class TriggerPipelineError(ActionExecutionError):
    """Raised when the Azure DevOps API returns an error while triggering a pipeline."""

    DEFAULT_STATUS_LABEL = "Pipeline trigger failed"

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "TriggerPipelineError":
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
