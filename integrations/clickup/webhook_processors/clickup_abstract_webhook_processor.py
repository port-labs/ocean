import hashlib
import hmac
from typing import Optional

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class ClickUpAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for ClickUp webhook processors.

    ClickUp webhooks are signed using HMAC-SHA256 with a shared secret.
    The signature is sent in the X-Signature header.

    Reference: https://developer.clickup.com/docs/webhooksignature
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Verify the webhook signature using HMAC-SHA256.

        The signature is computed as:
        HMAC-SHA256(webhook_secret, request_body)
        """
        webhook_secret: Optional[str] = ocean.integration_config.get(
            "clickup_webhook_secret"
        )

        if not webhook_secret:
            return True

        signature = headers.get("x-signature")
        if not signature:
            return False

        try:
            import json

            body = json.dumps(payload, separators=(",", ":"))

            expected_signature = hmac.new(
                webhook_secret.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
