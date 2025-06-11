import hashlib
import hmac
import json
from abc import abstractmethod, ABC
from datetime import datetime
from typing import Any, Coroutine, Optional

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEventRawResults,
    WebhookEvent,
)
from .events import GitHubWebhookEventType


class BaseWebhookProcessor(AbstractWebhookProcessor, ABC):
    """base processor for webhook events"""

    def __init__(self):
        super().__init__(
            WebhookEvent(
                trace_id=f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                payload=dict(),
                headers=dict(),
            )
        )
        self.webhook_secret = ocean.integration_config.get("webhook_secret", None)

    def _verify_signature(self, signature: str, data: dict[str, Any]) -> bool:
        if self.webhook_secret is None:
            logger.warning(
                "webhook_secret is not configured for GitHub integration. Skipping webhooks."
            )
            return False

        # encode web secret
        encoded_web_secret = (
            self.webhook_secret.encode()
            if isinstance(self.webhook_secret, str)
            else None
        )

        # serialize payload to bytes
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )

        # compare digest with secret
        mac = hmac.new(encoded_web_secret, msg=payload, digestmod=hashlib.sha256)
        expected = f"sha256={mac.hexdigest()}"
        return hmac.compare_digest(expected, signature)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """validate the event payload"""
        required_fields = ["hook", "sender"]
        return all(field in payload for field in required_fields)

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> bool:
        """handle webhook event"""
        results = await self.process_event(payload, resource.kind)
        return results is not None

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """authenticate webhook based on payload and headers"""
        raise NotImplementedError()

    @abstractmethod
    async def process_event(
        self, payload: EventPayload, kind: str
    ) -> WebhookEventRawResults:
        """process event payload"""
        raise NotImplementedError()

    @abstractmethod
    def get_event_type(self) -> GitHubWebhookEventType:
        """return the type of event of the webhook"""
        raise NotImplementedError()

    @abstractmethod
    async def validate_webhook(
        self,
        repo_slug: str,
        target_url: str,
        event_type: GitHubWebhookEventType,
    ) -> bool:
        """validate webhook event"""
        raise NotImplementedError()

    @abstractmethod
    async def create_webhook(
        self,
        webhook_url: str,
        repo_slug: str,
        name: Optional[str] = None,
    ) -> Coroutine[Any, Any, None] | None:
        """create webhook event"""
        raise NotImplementedError()
