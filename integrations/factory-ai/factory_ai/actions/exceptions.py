from __future__ import annotations

import json
from typing import Self

import httpx
from port_ocean.exceptions.execution_manager import ActionExecutionError


class FactoryActionError(ActionExecutionError):
    """Base for Factory.ai action failures reported verbatim to Port."""

    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        """Prefer Factory's shared ``FactoryApiError`` envelope fields."""
        try:
            body = response.json()
        except Exception:
            body = None

        detail: str | None = None
        if isinstance(body, dict):
            for key in ("detail", "title", "message", "error"):
                if (value := body.get(key)) is not None:
                    detail = value if isinstance(value, str) else json.dumps(value)
                    break

        if detail is None:
            detail = response.text.strip() or f"HTTP {response.status_code}"

        return cls(f"{prefix}: {detail}")


class InvalidActionParametersError(FactoryActionError):
    """Raised when an action run is missing required parameters."""

    DEFAULT_STATUS_LABEL = "Invalid inputs"


class ExecuteDroidError(FactoryActionError):
    """Raised when ``POST /api/v0/droid/execute`` fails or returns a bad body."""

    DEFAULT_STATUS_LABEL = "Execute failed"
