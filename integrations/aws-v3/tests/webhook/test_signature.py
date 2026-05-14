from __future__ import annotations

import base64
import datetime as dt
from typing import Any

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from aws.webhook.signature import HmacSignatureVerifier, SnsSignatureVerifier


CERT_URL = "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-test.pem"


def _build_self_signed_pem() -> tuple[bytes, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM), key


def _canonical_notification(payload: dict[str, Any]) -> str:
    fields = ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type")
    parts: list[str] = []
    for field in fields:
        value = payload.get(field)
        if value is None and field == "Subject":
            continue
        parts.append(field)
        parts.append(str(value))
    return "\n".join(parts) + "\n"


def _sign(canonical: str, key: rsa.RSAPrivateKey) -> str:
    digest = key.sign(canonical.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())
    return base64.b64encode(digest).decode("ascii")


def _make_http_client(pem_bytes: bytes) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pem_bytes)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_valid_sns_signature_accepts() -> None:
    pem_bytes, key = _build_self_signed_pem()
    payload: dict[str, Any] = {
        "Type": "Notification",
        "MessageId": "abc",
        "TopicArn": "arn:aws:sns:us-east-1:111111111111:t",
        "Message": "hello",
        "Timestamp": "2026-05-14T12:00:00Z",
    }
    canonical = _canonical_notification(payload)
    payload["Signature"] = _sign(canonical, key)
    payload["SigningCertURL"] = CERT_URL
    payload["SignatureVersion"] = "1"

    verifier = SnsSignatureVerifier(http_client=_make_http_client(pem_bytes))
    try:
        assert await verifier.verify(payload) is True
    finally:
        await verifier.aclose()


@pytest.mark.asyncio
async def test_tampered_body_rejected() -> None:
    pem_bytes, key = _build_self_signed_pem()
    payload: dict[str, Any] = {
        "Type": "Notification",
        "MessageId": "abc",
        "TopicArn": "arn:aws:sns:us-east-1:111111111111:t",
        "Message": "hello",
        "Timestamp": "2026-05-14T12:00:00Z",
    }
    canonical = _canonical_notification(payload)
    payload["Signature"] = _sign(canonical, key)
    payload["Message"] = "tampered"
    payload["SigningCertURL"] = CERT_URL
    payload["SignatureVersion"] = "1"

    verifier = SnsSignatureVerifier(http_client=_make_http_client(pem_bytes))
    try:
        assert await verifier.verify(payload) is False
    finally:
        await verifier.aclose()


@pytest.mark.asyncio
async def test_cert_url_outside_allowlist_rejected() -> None:
    pem_bytes, key = _build_self_signed_pem()
    payload: dict[str, Any] = {
        "Type": "Notification",
        "MessageId": "abc",
        "TopicArn": "arn:aws:sns:us-east-1:111111111111:t",
        "Message": "hello",
        "Timestamp": "2026-05-14T12:00:00Z",
        "Signature": _sign(_canonical_notification({}), key),
        "SigningCertURL": "https://attacker.example.com/cert.pem",
        "SignatureVersion": "1",
    }
    verifier = SnsSignatureVerifier(http_client=_make_http_client(pem_bytes))
    try:
        assert await verifier.verify(payload) is False
    finally:
        await verifier.aclose()


@pytest.mark.asyncio
async def test_missing_fields_rejected() -> None:
    verifier = SnsSignatureVerifier(http_client=_make_http_client(b""))
    try:
        assert await verifier.verify({"Type": "Notification"}) is False
    finally:
        await verifier.aclose()


def test_hmac_accepts_matching_signature() -> None:
    import hashlib
    import hmac

    verifier = HmacSignatureVerifier(secret="top-secret")
    body = b'{"hello":"world"}'
    digest = hmac.new(b"top-secret", body, hashlib.sha256).hexdigest()
    assert verifier.verify(body, digest) is True
    assert verifier.verify(body, f"sha256={digest}") is True


def test_hmac_rejects_mismatched_signature() -> None:
    verifier = HmacSignatureVerifier(secret="top-secret")
    body = b'{"hello":"world"}'
    assert verifier.verify(body, "deadbeef") is False
    assert verifier.verify(body, None) is False
    assert verifier.verify(body, "not-hex") is False
