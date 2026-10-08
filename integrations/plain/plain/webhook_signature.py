from __future__ import annotations

import hashlib
import hmac

from loguru import logger

from plain.constants import SIGNATURE_HEADER


def verify_plain_signature(
    body: bytes,
    headers: dict[str, str],
    secret: str | None,
) -> bool:
    """Verify ``Plain-Request-Signature`` (HMAC-SHA256 hex of the raw body).

    When no secret is configured, verification is skipped so local/dev installs
    can still receive events. Production installs should set ``webhookSecret``.
    """
    if not secret:
        logger.warning(
            "Skipping Plain webhook signature verification because webhookSecret "
            "is not configured"
        )
        return True

    received = _header_value(headers, SIGNATURE_HEADER)
    if not received:
        logger.error("Missing Plain-Request-Signature header")
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received, expected):
        logger.error("Invalid Plain webhook signature")
        return False
    return True


def _header_value(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None
