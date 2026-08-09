import json

import httpx


class InvalidActionParametersError(Exception):
    """Raised when an action run is missing required parameters."""


class MultipleOrganizationsNotSupportedError(Exception):
    """Raised when actions are invoked while multiple organizations are configured."""


class TriggerPipelineError(Exception):
    """Raised when the Azure DevOps API returns an error while triggering a pipeline."""

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
