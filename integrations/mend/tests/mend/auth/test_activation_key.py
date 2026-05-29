import base64
import json
from typing import Any

import pytest

from mend.auth.activation_key import (
    decode_activation_key,
    derive_base_url,
)
from mend.exceptions import MendAuthenticationError

# ── helpers ──────────────────────────────────────────────────────────────────

_CAESAR_OFFSET = 4


def _make_activation_key(payload: dict[str, Any]) -> str:
    """
    Inverse of the TypeScript caesarCipherDecrypt so tests can produce valid keys.
    Encode path: JSON payload → JWT → base64 → reverse → Caesar+4.
    """
    # Build a minimal unsigned JWT (header.payload.signature)
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    jwt_string = f"{header}.{body}."

    # base64-encode the JWT, then reverse, then Caesar+4
    b64 = base64.b64encode(jwt_string.encode()).decode()
    reversed_b64 = b64[::-1]
    encrypted = "".join(chr(ord(c) + _CAESAR_OFFSET) for c in reversed_b64)
    return encrypted


# ── decode_activation_key ─────────────────────────────────────────────────────


class TestDecodeActivationKey:
    def test_decodes_full_payload(self) -> None:
        payload = {
            "integratorEmail": "user@example.com",
            "userKey": "abc123",
            "wsEnvUrl": "https://saas.mend.io",
            "orgUuid": "org-uuid-001",
        }
        key = _make_activation_key(payload)
        result = decode_activation_key(key)
        assert result["integratorEmail"] == "user@example.com"
        assert result["userKey"] == "abc123"
        assert result["wsEnvUrl"] == "https://saas.mend.io"
        assert result["orgUuid"] == "org-uuid-001"

    def test_raises_on_bad_base64(self) -> None:
        with pytest.raises(
            MendAuthenticationError, match="Provide a valid Mend Activation key"
        ):
            decode_activation_key("not!!!valid")

    def test_raises_on_non_jwt_content(self) -> None:
        # Valid Caesar+reverse+base64 but payload is not a JWT
        raw = "not-a-jwt"
        b64 = base64.b64encode(raw.encode()).decode()
        reversed_b64 = b64[::-1]
        bad_key = "".join(chr(ord(c) + _CAESAR_OFFSET) for c in reversed_b64)
        with pytest.raises(
            MendAuthenticationError, match="Provide a valid Mend Activation key"
        ):
            decode_activation_key(bad_key)

    def test_raises_on_empty_input(self) -> None:
        with pytest.raises(
            MendAuthenticationError, match="Provide a valid Mend Activation key"
        ):
            decode_activation_key("")


# ── derive_base_url ───────────────────────────────────────────────────────────


class TestDeriveBaseUrl:
    def test_full_https_url(self) -> None:
        assert derive_base_url("https://saas.mend.io") == "https://api-saas.mend.io"

    def test_full_http_url(self) -> None:
        assert derive_base_url("http://saas.mend.io") == "https://api-saas.mend.io"

    def test_hostname_only(self) -> None:
        assert derive_base_url("saas.mend.io") == "https://api-saas.mend.io"

    def test_subdomain_preserved(self) -> None:
        assert derive_base_url("https://app.eu.mend.io") == "https://api-app.eu.mend.io"
