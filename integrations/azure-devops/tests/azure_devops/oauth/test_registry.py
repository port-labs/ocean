from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from azure_devops.oauth.registry import (
    _ADO_RESOURCE_ID,
    _SCOPES,
    register_oauth_provider,
)
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider


@pytest.fixture
def mock_ocean() -> Generator[MagicMock, None, None]:
    with patch("azure_devops.oauth.registry.ocean") as ocean:
        ocean.integration_config = {}
        ocean.config.identity_propagation.enabled = False
        ocean.config.integration.type = "azure-devops"
        ocean.register_oauth_provider = MagicMock()
        yield ocean


def test_scopes_include_ado_resource_and_offline_access() -> None:
    assert _ADO_RESOURCE_ID in _SCOPES
    assert "user_impersonation" in _SCOPES
    assert "offline_access" in _SCOPES


def test_register_is_noop_without_identity_oauth(mock_ocean: MagicMock) -> None:
    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_warns_when_ip_enabled_but_identity_oauth_missing(
    mock_ocean: MagicMock,
) -> None:
    mock_ocean.config.identity_propagation.enabled = True

    with patch("azure_devops.oauth.registry.logger") as logger:
        register_oauth_provider()

    logger.warning.assert_called_once()
    assert "identityOauthClientId" in logger.warning.call_args.args[0]
    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_builds_tenant_scoped_entra_provider(mock_ocean: MagicMock) -> None:
    mock_ocean.integration_config = {
        "identity_oauth_tenant_id": "tenant-1",
        "identity_oauth_client_id": "cid",
        "identity_oauth_client_secret": "csecret",
    }

    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_called_once()
    provider = mock_ocean.register_oauth_provider.call_args.args[0]
    assert isinstance(provider, OAuth2Provider)
    assert provider.target == "azure-devops"
    assert (
        provider._authorize_url
        == "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/authorize"
    )
    assert (
        provider._token_url
        == "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token"
    )
    assert provider._client_id == "cid"
    assert provider._client_secret == "csecret"
    assert provider._scopes == _SCOPES


def test_registered_provider_authorization_url_requests_offline_access(
    mock_ocean: MagicMock,
) -> None:
    mock_ocean.integration_config = {
        "identity_oauth_tenant_id": "tenant-1",
        "identity_oauth_client_id": "cid",
        "identity_oauth_client_secret": "csecret",
    }

    register_oauth_provider()
    provider = mock_ocean.register_oauth_provider.call_args.args[0]
    url = provider.authorization_url("https://ocean.acme.com/callback", "signed-state")

    assert url.startswith(
        "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/authorize?"
    )
    assert "offline_access" in url
    assert "state=signed-state" in url
    assert "response_type=code" in url
