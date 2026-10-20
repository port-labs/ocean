import json

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class InvalidActionParametersException(ActionExecutionError):
    """Raised when an action's input parameters are missing or invalid."""

    DEFAULT_STATUS_LABEL = "Invalid inputs"


class SessionBusyError(ActionExecutionError):
    """Raised when a follow-up is sent while the session is still on a turn."""

    DEFAULT_STATUS_LABEL = "Session busy"


class DevinApiError(ActionExecutionError):
    """Raised when the Devin API rejects a request made by an action."""

    DEFAULT_STATUS_LABEL = "Devin error"

    @classmethod
    def from_http_error(cls, error: httpx.HTTPError, prefix: str) -> "DevinApiError":
        if isinstance(error, httpx.HTTPStatusError):
            return cls(f"{prefix}: {_response_detail(error.response)}")
        return cls(f"{prefix}: {error}")


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        body = None

    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            if (value := body.get(key)) is not None:
                return value if isinstance(value, str) else json.dumps(value)

    text = response.text.strip()
    return text or f"HTTP {response.status_code}"
