"""Langfuse prompt webhook HMAC (`x-langfuse-signature: t=...,v1=...`)."""

from __future__ import annotations

import hashlib
import hmac

from port_ocean.context.ocean import ocean


SIGNATURE_HEADER = "x-langfuse-signature"


def get_webhook_secret() -> str | None:
    value = ocean.integration_config.get("webhook_secret")
    if isinstance(value, str) and value:
        return value
    return None


def verify_langfuse_signature(
    raw_body: str, signature_header: str, secret: str
) -> bool:
    try:
        ts_pair, sig_pair = signature_header.split(",", 1)
    except ValueError:
        return False

    if "=" not in ts_pair or "=" not in sig_pair:
        return False

    timestamp = ts_pair.split("=", 1)[1]
    received_sig_hex = sig_pair.split("=", 1)[1]
    expected_sig_hex = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{raw_body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    try:
        return hmac.compare_digest(
            bytes.fromhex(received_sig_hex), bytes.fromhex(expected_sig_hex)
        )
    except ValueError:
        return False
