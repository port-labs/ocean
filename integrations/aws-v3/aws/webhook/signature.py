from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from typing import Any, Final, Iterable
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from loguru import logger


_DEFAULT_ALLOWED_HOST_SUFFIXES: Final[tuple[str, ...]] = ("amazonaws.com",)
_NOTIFICATION_FIELDS: Final[tuple[str, ...]] = (
    "Message",
    "MessageId",
    "Subject",
    "Timestamp",
    "TopicArn",
    "Type",
)
_SUBSCRIPTION_FIELDS: Final[tuple[str, ...]] = (
    "Message",
    "MessageId",
    "SubscribeURL",
    "Timestamp",
    "Token",
    "TopicArn",
    "Type",
)


class SnsSignatureVerifier:
    """Verifies the X.509 signature on an SNS HTTPS message.

    Caches signing certificates by URL — a busy topic shouldn't trigger
    a fresh cert fetch on every delivery.
    """

    def __init__(
        self,
        allowed_host_suffixes: Iterable[str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._allowed_host_suffixes = tuple(
            allowed_host_suffixes or _DEFAULT_ALLOWED_HOST_SUFFIXES
        )
        self._cert_cache: dict[str, rsa.RSAPublicKey] = {}
        self._cache_lock = asyncio.Lock()
        self._http = http_client or httpx.AsyncClient(timeout=5.0)
        self._owns_client = http_client is None

    async def verify(self, message: dict[str, Any]) -> bool:
        try:
            signing_cert_url = message["SigningCertURL"]
            signature_b64 = message["Signature"]
            signature_version = message.get("SignatureVersion", "1")
        except KeyError as exc:
            logger.warning(f"SNS signature: missing required field {exc}")
            return False

        if not self._is_url_allowed(signing_cert_url):
            logger.warning(
                f"SNS signature: rejected cert URL '{signing_cert_url}'"
                " (host not in allowlist)"
            )
            return False

        canonical = self._canonical_string(message)
        if canonical is None:
            logger.warning("SNS signature: unable to build canonical string")
            return False

        try:
            public_key = await self._get_public_key(signing_cert_url)
        except Exception as exc:
            logger.warning(f"SNS signature: failed to load cert: {exc}")
            return False

        algorithm: hashes.HashAlgorithm
        algorithm = hashes.SHA256() if signature_version == "2" else hashes.SHA1()

        try:
            public_key.verify(
                base64.b64decode(signature_b64),
                canonical.encode("utf-8"),
                padding.PKCS1v15(),
                algorithm,
            )
            return True
        except InvalidSignature:
            logger.warning("SNS signature: signature did not verify")
            return False

    def _is_url_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = parsed.hostname or ""
        # SNS signing certs are always served from sns.<region>.amazonaws.com
        # or sns.amazonaws.com. Pin the leading subdomain so a permissive
        # `amazonaws.com` suffix can't be abused by any other AWS service.
        if not (host == "sns.amazonaws.com" or host.startswith("sns.")):
            return False
        return any(
            host == suffix or host.endswith("." + suffix)
            for suffix in self._allowed_host_suffixes
        )

    @staticmethod
    def _canonical_string(message: dict[str, Any]) -> str | None:
        msg_type = message.get("Type")
        if msg_type == "Notification":
            fields = _NOTIFICATION_FIELDS
        elif msg_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
            fields = _SUBSCRIPTION_FIELDS
        else:
            return None

        parts: list[str] = []
        for field in fields:
            value = message.get(field)
            if value is None:
                if field == "Subject":
                    continue  # optional
                return None
            parts.append(field)
            parts.append(str(value))
        return "\n".join(parts) + "\n"

    async def _get_public_key(self, url: str) -> rsa.RSAPublicKey:
        async with self._cache_lock:
            cached = self._cert_cache.get(url)
            if cached is not None:
                return cached
        response = await self._http.get(url)
        response.raise_for_status()
        cert = x509.load_pem_x509_certificate(response.content)
        public_key = cert.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("SNS signing cert did not contain an RSA key")
        async with self._cache_lock:
            self._cert_cache[url] = public_key
        return public_key

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()


class HmacSignatureVerifier:
    """Constant-time HMAC-SHA256 comparison against a shared secret.

    Verifies a hex-encoded digest in `X-Port-Signature`. Tolerates both
    a raw hex digest and a `sha256=<hex>` form.
    """

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def verify(self, raw_body: bytes, provided_signature: str | None) -> bool:
        if not provided_signature:
            return False
        provided = provided_signature.strip()
        if provided.startswith("sha256="):
            provided = provided[len("sha256=") :]
        try:
            provided_bytes = bytes.fromhex(provided)
        except ValueError:
            return False
        expected = hmac.new(self._secret, raw_body, hashlib.sha256).digest()
        return hmac.compare_digest(expected, provided_bytes)


__all__ = [
    "SnsSignatureVerifier",
    "HmacSignatureVerifier",
]
