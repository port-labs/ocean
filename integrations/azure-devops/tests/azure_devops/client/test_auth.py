import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_devops.client.auth import (
    ACCOUNT_MODE_MULTIPLE,
    ACCOUNT_MODE_SINGLE,
    ADO_SCOPE,
    PatAuthProvider,
    ServicePrincipalAuthProvider,
    build_auth_provider,
)


@pytest.mark.asyncio
async def test_pat_auth_provider_returns_basic_header() -> None:
    provider = PatAuthProvider("my-test-pat")
    headers = await provider.get_auth_headers()
    expected = base64.b64encode(b":my-test-pat").decode()
    assert headers == {"Authorization": f"Basic {expected}"}


@pytest.mark.asyncio
async def test_sp_auth_provider_returns_bearer_header() -> None:
    mock_credential = AsyncMock()
    mock_token = MagicMock()
    mock_token.token = "fake-bearer-token"
    mock_credential.get_token.return_value = mock_token

    provider = ServicePrincipalAuthProvider(mock_credential)
    headers = await provider.get_auth_headers()

    assert headers == {"Authorization": "Bearer fake-bearer-token"}
    mock_credential.get_token.assert_called_once_with(ADO_SCOPE)


def test_build_auth_provider_single_account_mode() -> None:
    provider = build_auth_provider(
        {"account_mode": ACCOUNT_MODE_SINGLE, "personal_access_token": "my-pat"}
    )
    assert isinstance(provider, PatAuthProvider)


def test_build_auth_provider_single_account_mode_default() -> None:
    """account_mode defaults to Single Account when omitted."""
    provider = build_auth_provider({"personal_access_token": "my-pat"})
    assert isinstance(provider, PatAuthProvider)


def test_build_auth_provider_multiple_accounts_mode() -> None:
    with patch("azure_devops.client.auth.DefaultAzureCredential") as mock_dac:
        mock_dac.return_value = MagicMock()
        provider = build_auth_provider(
            {
                "account_mode": ACCOUNT_MODE_MULTIPLE,
                "client_id": "cid",
                "client_secret": "csecret",
                "tenant_id": "tid",
            }
        )
    assert isinstance(provider, ServicePrincipalAuthProvider)
    mock_dac.assert_called_once()


def test_build_auth_provider_single_account_missing_pat() -> None:
    with pytest.raises(ValueError, match="personal_access_token"):
        build_auth_provider({"account_mode": ACCOUNT_MODE_SINGLE})


def test_build_auth_provider_multiple_accounts_missing_sp_field() -> None:
    with pytest.raises(ValueError, match="client_secret"):
        build_auth_provider({"account_mode": ACCOUNT_MODE_MULTIPLE, "client_id": "cid"})


def test_build_auth_provider_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown account_mode"):
        build_auth_provider({"account_mode": "invalid"})
