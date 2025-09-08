from loguru import logger
import hmac
import hashlib
from typing import Optional

from github.settings import SETTINGS
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class BaseWebhookProcessorMixin(AbstractWebhookProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Authenticate the request by verifying GitHub signature using the provided payload and headers
        return await self._verify_webhook_signature(payload, headers)

    async def _verify_webhook_signature(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Validate GitHub webhook using HMAC-SHA256 (or fallback to SHA1) signature.

        GitHub sends signatures in the headers:
        - X-Hub-Signature-256: "sha256=<hexdigest>"
        - X-Hub-Signature: "sha1=<hexdigest>"

        If no secret is configured, skip verification.
        """
        secret: Optional[str] = SETTINGS.webhook_secret
        if not secret:
            logger.info("No webhook_secret configured; skipping signature verification.")
            return True

        # Headers are case-insensitive, but dict may be lower-cased already
        sig256 = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
        sig1 = headers.get("x-hub-signature") or headers.get("X-Hub-Signature")

        # Compute signature over the JSON payload
        # Note: GitHub signs the raw request body. We approximate with a compact JSON dump of the payload.
        # For exact verification, pass the raw body to this method instead.
        try:
            import json

            body: bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except Exception:
            logger.exception("Failed to serialize webhook payload for signature verification")
            return False

        if sig256 and sig256.startswith("sha256="):
            expected = sig256.split("=", 1)[1]
            computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            valid = hmac.compare_digest(expected, computed)
            if not valid:
                logger.warning("GitHub webhook SHA256 signature mismatch")
            return valid

        if sig1 and sig1.startswith("sha1="):
            expected = sig1.split("=", 1)[1]
            computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha1).hexdigest()
            valid = hmac.compare_digest(expected, computed)
            if not valid:
                logger.warning("GitHub webhook SHA1 signature mismatch")
            return valid

        logger.warning("Missing GitHub signature headers; expected X-Hub-Signature-256 or X-Hub-Signature")
        return False

    def _get_github_event_type(self, headers: EventHeaders) -> str | None:
        """Return the GitHub event type header in a case-insensitive way."""
        if not isinstance(headers, dict):
            return None
        return (
            headers.get("x-github-event")
            or headers.get("X-GitHub-Event")
            or headers.get("X-GITHUB-EVENT")
        )

    