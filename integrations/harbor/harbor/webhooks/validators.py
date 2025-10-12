"""Webhook signature verification."""
import hashlib
import hmac
from loguru import logger


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Harbor webhook signature."""
    if not secret or not signature:
        return True

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    is_valid = hmac.compare_digest(signature, expected_signature)
    if not is_valid:
        logger.warning("Webhook signature verification failed")

    return is_valid
