"""Tests for `aws.webhook.security.signature`.

These tests are pure, deterministic, and use only stdlib `hmac`/`hashlib`.
No network, AWS, or Ocean dependencies.
"""

import hmac
from typing import Any, cast

import pytest

from aws.webhook.security.signature import (
    SIGNATURE_PREFIX,
    compute_signature,
    verify_signature,
)


SECRET: str = "test-secret"
BODY: bytes = b'{"hello":"world"}'

EXPECTED_HEX: str = "84cc33df716ed0b0598f07437c94069ace3730358778a592bd6bbd1423d111f3"
"""Hand-computed digest for ``HMAC-SHA256(SECRET, BODY)``. Pinning the value
guards against accidental drift in the encoding, prefix, or hash algorithm.
"""


def test_compute_signature_known_vector() -> None:
    """`compute_signature(secret, body)` -> stable known-good HMAC-SHA256 hex
    against a hand-computed vector."""

    assert compute_signature(SECRET, BODY) == f"{SIGNATURE_PREFIX}{EXPECTED_HEX}"


def test_verify_signature_accepts_valid() -> None:
    """A header value computed with the same secret and body verifies True."""

    header = compute_signature(SECRET, BODY)
    assert verify_signature(SECRET, BODY, header) is True


def test_verify_signature_rejects_tampered_body() -> None:
    """If the body is altered after signing, verification fails."""

    header = compute_signature(SECRET, BODY)
    assert verify_signature(SECRET, BODY + b" tampered", header) is False


def test_verify_signature_rejects_missing_header() -> None:
    """`header_value=None` and empty strings both verify False."""

    assert verify_signature(SECRET, BODY, None) is False
    assert verify_signature(SECRET, BODY, "") is False


def test_verify_signature_rejects_malformed_header() -> None:
    """Headers without the canonical ``sha256=`` prefix are rejected outright,
    before any HMAC computation."""

    assert verify_signature(SECRET, BODY, "abc") is False
    assert verify_signature(SECRET, BODY, "sha1=deadbeef") is False
    assert verify_signature(SECRET, BODY, "SHA256=deadbeef") is False


def test_verify_signature_rejects_invalid_signature() -> None:
    """Well-formed but mismatched signatures (wrong secret, garbage digest)
    return False."""

    wrong_secret_header = compute_signature("different-secret", BODY)
    assert verify_signature(SECRET, BODY, wrong_secret_header) is False

    garbage_header = f"{SIGNATURE_PREFIX}{'0' * 64}"
    assert verify_signature(SECRET, BODY, garbage_header) is False


def test_uses_compare_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """`verify_signature` must use `hmac.compare_digest` for the comparison
    (constant-time) - verified by patching the symbol as it is bound inside
    the module under test and asserting a single call."""

    calls: list[int] = []
    real_compare_digest = hmac.compare_digest

    def spy(a: str | bytes, b: str | bytes) -> bool:
        calls.append(1)
        return real_compare_digest(cast(Any, a), cast(Any, b))

    monkeypatch.setattr("aws.webhook.security.signature.hmac.compare_digest", spy)

    header = compute_signature(SECRET, BODY)
    assert verify_signature(SECRET, BODY, header) is True
    assert len(calls) == 1
