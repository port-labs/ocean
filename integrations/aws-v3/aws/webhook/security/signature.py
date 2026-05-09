"""HMAC-SHA256 signing and verification helpers for inbound AWS live events.

The customer-side forwarder Lambda computes a signature over the raw HTTP body
using the shared `webhookSecret` and includes it in the
``X-Port-Signature: sha256=<hex>`` request header. The Ocean integration
verifies that header here.

This mirrors the GitHub integration's signature path
(see `_GithubAbstractWebhookProcessor._verify_webhook_signature` in
`integrations/github/github/webhook/webhook_processors/github_abstract_webhook_processor.py`)
but uses a Port-namespaced header to avoid leaking provider semantics.
"""

import hashlib
import hmac


SIGNATURE_HEADER: str = "x-port-signature"
"""Lowercase header name. ASGI normalises headers to lowercase, which is what
Ocean's `WebhookEvent.headers` exposes; keep the constant lowercase to make
header lookups case-correct without per-call ``.lower()``.
"""

SIGNATURE_PREFIX: str = "sha256="
"""All valid signature header values start with this prefix, e.g.
``sha256=ab12...``. The prefix is preserved end-to-end so the scheme is
self-describing if rotated to a different hash in the future."""


def compute_signature(secret: str, body: bytes) -> str:
    """Return ``"sha256=<hex>"`` for ``HMAC-SHA256(secret, body)``.

    Used in tests and by any Python code that signs payloads (the production
    forwarder is a Lambda that does the same in its own process). The full
    header value is returned, prefix included, so callers never have to
    concatenate ``SIGNATURE_PREFIX`` themselves.

    Args:
        secret: shared secret. Encoded as UTF-8 before HMAC. This makes the
            contract unambiguous if a non-ASCII secret is ever passed.
        body: raw request body as bytes. Callers must pass exactly the bytes
            they will transmit; re-serialising parsed JSON will produce a
            different signature due to whitespace/ordering differences.
    """

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, header_value: str | None) -> bool:
    """Constant-time HMAC verification.

    Args:
        secret: shared secret from ``ocean.integration_config["webhook_secret"]``.
        body: raw request body as bytes (do **not** re-serialise the parsed
            JSON; whitespace differences will break verification).
        header_value: the value of the ``X-Port-Signature`` request header,
            or ``None`` if absent.

    Returns:
        ``True`` only when ``header_value`` exists, starts with
        :data:`SIGNATURE_PREFIX`, and the suffix matches the recomputed HMAC
        compared with ``hmac.compare_digest``. ``False`` for missing,
        malformed, or mismatched signatures.
    """

    if not header_value or not header_value.startswith(SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, header_value)
