import hmac
import hashlib
from starlette.requests import Request
from loguru import logger
from typing import Optional

async def validate_webhook_payload(request: Request, secret: str) -> bool:
    """
    Validate a Bitbucket webhook payload using a shared secret.

    This function calculates the HMAC-SHA256 signature of the request body and compares it with the
    signature provided in the 'X-Hub-Signature' header to ensure payload authenticity.

    Args:
        request (Request): The incoming webhook request.
        secret (str): The shared secret used to compute the HMAC signature.

    Returns:
        bool: True if the computed signature matches the header, False otherwise.
    """
    try:
        payload: bytes = await request.body()
    except Exception as error:
        logger.error(f"Failed to read request body: {error}")
        return False

    signature: Optional[str] = request.headers.get("X-Hub-Signature")
    if not signature:
        logger.error("Missing 'X-Hub-Signature' header")
        return False

    computed_hmac = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256)
    expected_signature: str = "sha256=" + computed_hmac.hexdigest()

    if hmac.compare_digest(signature, expected_signature):
        logger.info("Webhook payload validation succeeded")
        return True
    else:
        logger.error("Webhook payload validation failed")
        return False
