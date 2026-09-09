import json

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""


class TriggerIncidentError(ActionExecutionError):
    """Raised when the PagerDuty API returns an error while creating an incident."""

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "TriggerIncidentError":
        return cls(f"{prefix}: {cls._response_detail(response)}")

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            for key in ("error", "message", "errors"):
                if (value := body.get(key)) is not None:
                    return value if isinstance(value, str) else json.dumps(value)

        text = response.text.strip()
        return text or f"HTTP {response.status_code}"
