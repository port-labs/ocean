"""
SNS message signature validation.

SNS signs every HTTP/HTTPS notification with a certificate it fetches from
a URL it includes in the message. We verify the signature before processing
any event to prevent spoofing.

Reference:
  https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html
"""

import base64
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from loguru import logger

# SNS certificates always come from *.amazonaws.com
_SNS_CERT_URL_PATTERN = re.compile(
    r"^https://sns\.[a-z0-9\-]+\.amazonaws\.com/.*\.pem$"
)


def _build_string_to_sign(message: dict[str, Any]) -> bytes:
    """
    Build the canonical string SNS signs.
    The fields and their order differ by message type.
    """
    msg_type = message.get("Type", "")

    if msg_type == "Notification":
        fields = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]
    elif msg_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
        fields = [
            "Message",
            "MessageId",
            "SubscribeURL",
            "Timestamp",
            "Token",
            "TopicArn",
            "Type",
        ]
    else:
        raise ValueError(f"Unknown SNS message type: {msg_type!r}")

    parts = []
    for field in fields:
        if field in message:
            parts.append(f"{field}\n{message[field]}\n")

    return "".join(parts).encode("utf-8")


async def _fetch_certificate(cert_url: str) -> bytes:
    """Download the SNS signing certificate. No caching — keep it simple."""
    async with aiohttp.ClientSession() as session:
        async with session.get(cert_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.read()


async def validate_sns_signature(raw_body: bytes) -> dict[str, Any]:
    """
    Parse, validate, and return the SNS message dict.

    Raises ValueError if validation fails — callers should return HTTP 401.
    """
    try:
        message: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in SNS message: {exc}") from exc

    cert_url: str = message.get("SigningCertURL", "")
    signature_b64: str = message.get("Signature", "")
    sign_version: str = message.get("SignatureVersion", "")

    if not cert_url or not signature_b64:
        raise ValueError("SNS message missing SigningCertURL or Signature")

    if not _SNS_CERT_URL_PATTERN.match(cert_url):
        raise ValueError(f"SNS certificate URL failed domain validation: {cert_url!r}")

    if sign_version != "1":
        raise ValueError(f"Unsupported SNS SignatureVersion: {sign_version!r}")

    cert_pem = await _fetch_certificate(cert_url)
    cert = load_pem_x509_certificate(cert_pem)
    public_key = cert.public_key()

    string_to_sign = _build_string_to_sign(message)
    signature = base64.b64decode(signature_b64)

    try:
        public_key.verify(signature, string_to_sign, padding.PKCS1v15(), hashes.SHA1())  # type: ignore[arg-type]
    except Exception as exc:
        raise ValueError(f"SNS signature verification failed: {exc}") from exc

    logger.debug(f"[webhook] SNS signature valid for message {message.get('MessageId')}")
    return message
