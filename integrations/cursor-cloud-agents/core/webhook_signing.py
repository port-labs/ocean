"""Per-run webhook secret derivation and HMAC verification.

Mirrors `apps/workflow-service/src/core/utils/cursorCallbackUtils.ts`
(`deriveWebhookSecret` / `verifyHmacSignature`): rather than asking the
customer to configure a static `cursorWebhookSecret`, the secret is derived
on demand from Ocean's own Port client secret (`ocean.config.port.client_secret`,
always present - no extra customer setup), the organization id (like
`deriveWebhookSecret`'s `orgId`, scoping the secret to the organization so it
can't be replayed across organizations sharing the same Ocean deployment),
and the Port run id embedded in the per-run webhook URL path (see
`actions.utils.build_webhook_url` and `actions.utils.WEBHOOK_PATH`).
Deriving from the URL-embedded run id (rather than looking one up from the
payload) means verification keeps working for late/duplicate webhook
deliveries after the run is no longer tracked as in-progress.

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


async def derive_webhook_secret(run_id: str) -> str:
    org_id = await _get_org_id()
    client_secret = ocean.config.port.client_secret
    message = f"{org_id}:{run_id}"
    return hmac.new(
        client_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(secret: str, raw_body: str, signature_header: str) -> bool:
    expected = (
        "sha256="
        + hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
