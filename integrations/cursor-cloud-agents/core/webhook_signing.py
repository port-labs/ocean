"""Webhook HMAC using the configured installation secret.

When `webhookSigningSecret` is set, that value is sent to Cursor as the webhook
secret and used to verify `X-Webhook-Signature` on incoming callbacks.
"""

from __future__ import annotations

import hashlib
import hmac

from port_ocean.context.ocean import ocean


def get_webhook_signing_secret() -> str | None:
    value = ocean.integration_config.get("webhook_signing_secret")
    if isinstance(value, str) and value:
        return value
    return None


def verify_hmac_signature(secret: str, raw_body: str, signature_header: str) -> bool:
    expected = (
        "sha256="
        + hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
