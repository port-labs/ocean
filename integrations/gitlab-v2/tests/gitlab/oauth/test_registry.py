from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from gitlab.oauth.registry import _DEFAULT_HOST, _SCOPES, register_oauth_provider
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider


@pytest.fixture
def mock_ocean() -> Generator[MagicMock, None, None]:
    with patch("gitlab.oauth.registry.ocean") as ocean:
        ocean.integration_config = {}
        ocean.config.identity_propagation.enabled = False
        ocean.config.integration.type = "gitlab-v2"
        ocean.register_oauth_provider = MagicMock()
        yield ocean


def test_register_is_noop_without_identity_oauth(mock_ocean: MagicMock) -> None:
    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_warns_when_ip_enabled_but_identity_oauth_missing(
    mock_ocean: MagicMock,
) -> None:
    mock_ocean.config.identity_propagation.enabled = True

    with patch("gitlab.oauth.registry.logger") as logger:
        register_oauth_provider()

    logger.warning.assert_called_once()
    assert "identityOauthClientId" in logger.warning.call_args.args[0]
    mock_ocean.register_oauth_provider.assert_not_called()


def test_register_builds_gitlab_provider(mock_ocean: MagicMock) -> None:
    mock_ocean.integration_config = {
        "gitlab_host": "https://gitlab.example.com",
        "identity_oauth_client_id": "cid",
        "identity_oauth_client_secret": "csecret",
    }

    register_oauth_provider()

    mock_ocean.register_oauth_provider.assert_called_once()
    provider = mock_ocean.register_oauth_provider.call_args.args[0]
    assert isinstance(provider, OAuth2Provider)
    assert provider.target == "gitlab-v2"
    assert provider._authorize_url == "https://gitlab.example.com/oauth/authorize"
    assert provider._token_url == "https://gitlab.example.com/oauth/token"
    assert provider._client_id == "cid"
    assert provider._client_secret == "csecret"
    assert provider._scopes == _SCOPES


def test_register_defaults_to_gitlab_com_host(mock_ocean: MagicMock) -> None:
    mock_ocean.integration_config = {
        "identity_oauth_client_id": "cid",
        "identity_oauth_client_secret": "csecret",
    }

    register_oauth_provider()

    provider = mock_ocean.register_oauth_provider.call_args.args[0]
    assert provider._authorize_url == f"{_DEFAULT_HOST}/oauth/authorize"
    assert provider._token_url == f"{_DEFAULT_HOST}/oauth/token"
