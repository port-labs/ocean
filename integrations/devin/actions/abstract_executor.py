import json

import httpx
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.client_factory import create_devin_client
from core.sessions import DevinSessions


class DevinApiError(ActionExecutionError):
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


class AbstractDevinExecutor(AbstractExecutor):
    # `AbstractExecutor` only declares this as a type annotation, so without this
    # default `execution_manager.register_executor` raises `AttributeError`.
    # Devin has no webhooks: tracked runs are completed by the `SessionTracker`.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.sessions = DevinSessions(create_devin_client())

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0
