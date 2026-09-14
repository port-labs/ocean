import hashlib
import hmac
from unittest.mock import MagicMock, patch

from core.webhook_signing import get_webhook_signing_secret, verify_hmac_signature


def test_get_webhook_signing_secret_returns_configured_value() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"webhook_signing_secret": "secret-123"}
    with patch("core.webhook_signing.ocean", mock_ocean):
        assert get_webhook_signing_secret() == "secret-123"


def test_get_webhook_signing_secret_returns_none_when_missing() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}
    with patch("core.webhook_signing.ocean", mock_ocean):
        assert get_webhook_signing_secret() is None


def test_verify_hmac_signature_matches_sha256_header() -> None:
    body = '{"id":"bc-1"}'
    header = "sha256=" + hmac.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
    assert verify_hmac_signature("secret", body, header) is True
    assert verify_hmac_signature("other", body, header) is False
