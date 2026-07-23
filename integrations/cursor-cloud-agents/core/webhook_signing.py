"""Per-run webhook secret derivation and HMAC verification.

When `webhookSigningSecret` is configured on the integration, the secret sent to
Cursor and used to verify incoming callbacks is derived per run from that
installation secret, the Port organization id, and the Port run id embedded in
the per-run webhook URL path (see `actions.utils.build_webhook_url` and
`actions.utils.WEBHOOK_PATH`). Deriving from the URL-embedded run id (rather
than looking one up from the payload) means verification keeps working for
late/duplicate webhook deliveries after the run is no longer tracked as
in-progress.

The org id never changes for the lifetime of the process, so it's fetched
from Port once and cached in-module rather than on every derive/verify call.
"""

from __future__ import annotations

import hashlib
import hmac

from port_ocean.context.ocean import ocean

_org_id_cache: str | None = None


async def _get_org_id() -> str:
    global _org_id_cache
    if _org_id_cache is None:
        _org_id_cache = await ocean.port_client.get_org_id()
    return _org_id_cache


def get_webhook_signing_secret() -> str | None:
    value = ocean.integration_config.get("webhook_signing_secret")
    if isinstance(value, str) and value:
        return value
    return None


async def derive_webhook_secret(run_id: str) -> str | None:
    signing_secret = get_webhook_signing_secret()
    if signing_secret is None:
        return None
    org_id = await _get_org_id()
    message = f"{org_id}:{run_id}"
    return hmac.new(
        signing_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(secret: str, raw_body: str, signature_header: str) -> bool:
    expected = (
        "sha256="
        + hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
