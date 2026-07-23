from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.webhook_signing as webhook_signing
from core.webhook_signing import derive_webhook_secret, get_webhook_signing_secret


@pytest.fixture(autouse=True)
def _reset_org_id_cache() -> None:
    webhook_signing._org_id_cache = None


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


@pytest.mark.asyncio
async def test_derive_webhook_secret_returns_none_when_not_configured() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}
    with patch("core.webhook_signing.ocean", mock_ocean):
        assert await derive_webhook_secret("run-1") is None


@pytest.mark.asyncio
async def test_derive_webhook_secret_uses_installation_secret() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {
        "webhook_signing_secret": "installation-secret",
    }
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="org-1")
    with patch("core.webhook_signing.ocean", mock_ocean):
        secret = await derive_webhook_secret("run-1")
    assert secret != "installation-secret"
    assert len(secret) == 64
