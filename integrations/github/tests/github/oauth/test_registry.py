from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from github.oauth.registry import _SCOPES, oauth_web_host, register_oauth_provider
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider


@pytest.fixture
def mock_ocean() -> Generator[MagicMock, None, None]:
    with patch("github.oauth.registry.ocean") as ocean:
        ocean.integration_config = {}
        ocean.config.identity_propagation.enabled = False
        ocean.config.integration.type = "github"
        ocean.register_oauth_provider = MagicMock()
        yield ocean


def test_oauth_web_host_maps_github_cloud_api_host() -> None:
    assert oauth_web_host("https://api.github.com") == "https://github.com"
    assert oauth_web_host("https://api.github.com/") == "https://github.com"


def test_oauth_web_host_maps_enterprise_api_host() -> None:
    assert oauth_web_host("https://ghe.example.com/api/v3") == "https://ghe.example.com"


def test_register_is_noop_without_identity_oauth(mock_ocean: MagicMock) -> None:
    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_warns_when_ip_enabled_but_identity_oauth_missing(
    mock_ocean: MagicMock,
) -> None:
    mock_ocean.config.identity_propagation.enabled = True

    with patch("github.oauth.registry.logger") as logger:
        register_oauth_provider()

    logger.warning.assert_called_once()
    assert "identityOauthClientId" in logger.warning.call_args.args[0]
    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_builds_github_provider(mock_ocean: MagicMock) -> None:
    mock_ocean.integration_config = {
        "github_host": "https://api.github.com",
        "identity_oauth_client_id": "cid",
        "identity_oauth_client_secret": "csecret",
    }

    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_called_once()
    provider = mock_ocean.register_oauth_provider.call_args.args[0]
    assert isinstance(provider, OAuth2Provider)
    assert provider.target == "github"
    assert provider._authorize_url == "https://github.com/login/oauth/authorize"
    assert provider._token_url == "https://github.com/login/oauth/access_token"
    assert provider._client_id == "cid"
    assert provider._client_secret == "csecret"
    assert provider._scopes == _SCOPES
