from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping


class WebhookSignatureError(Exception):
    pass


def _decode_signing_secret(secret: str) -> bytes:
    normalized = secret.strip()
    if normalized.startswith("whsec_"):
        normalized = normalized.removeprefix("whsec_")
    return base64.b64decode(normalized)


def verify_standard_webhook(
    payload: bytes,
    headers: Mapping[str, str],
    *,
    secret: str,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Standard Webhooks (OpenAI / Foundry) delivery headers."""
    msg_id = _header(headers, "webhook-id")
    timestamp = _header(headers, "webhook-timestamp")
    signature_header = _header(headers, "webhook-signature")
    if not msg_id or not timestamp or not signature_header:
        raise WebhookSignatureError("Missing Standard Webhooks headers")

    try:
        ts = int(timestamp)
    except ValueError as error:
        raise WebhookSignatureError("Invalid webhook timestamp") from error
    if abs(time.time() - ts) > tolerance_seconds:
        raise WebhookSignatureError("Webhook timestamp outside tolerance")

    key = _decode_signing_secret(secret)
    signed = f"{msg_id}.{timestamp}.{payload.decode('utf-8')}".encode()
    expected = hmac.new(key, signed, hashlib.sha256).digest()

    for part in signature_header.split():
        if not part.startswith("v1,"):
            continue
        received = base64.b64decode(part.removeprefix("v1,"))
        if hmac.compare_digest(received, expected):
            return
    raise WebhookSignatureError("Webhook signature mismatch")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
