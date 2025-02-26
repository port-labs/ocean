import hmac
import hashlib
from starlette.requests import Request
from loguru import logger


async def validate_webhook_payload(request: Request, secret: str) -> bool:
    """Validate the Bitbucket webhook payload using the secret."""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature")

    if not signature:
        logger.error("Missing X-Hub-Signature header")
        return False

    hash_object = hmac.new(secret.encode(), payload, hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(signature, expected_signature)
