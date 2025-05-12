import hmac
import hashlib
import json
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload


def authenticate_github_webhook(payload: EventPayload, headers: EventHeaders) -> bool:
    secret = ocean.integration_config.get("github_webhook_secret")
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET is not set")
        return False
    received_signature = headers.get("x-hub-signature-256")
    if not received_signature:
        logger.error("Missing X-Hub-Signature-256 header")
        return False
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    computed_signature = (
        "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(received_signature, computed_signature):
        logger.error("Signature verification failed for workflow_run event")
        return False
    return True
