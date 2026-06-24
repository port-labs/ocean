from unittest.mock import AsyncMock, patch

import pytest

from github.clients.auth.github_app_authenticator import (
    GitHubAppAuthenticator,
    reset_installation_index,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.client_factory import _list_auth_scopes
from github.helpers.exceptions import MissingCredentials

PAT_CONFIG = {
    "github_token": "pat",
    "github_app_id": "app",
    "github_app_private_key": "key",
    "github_host": "https://api.github.com",
}

APP_CONFIG = {
    "github_app_id": "app",
    "github_app_private_key": "key",
    "github_host": "https://api.github.com",
}


@pytest.fixture(autouse=True)
def _clear_installation_index() -> None:
    reset_installation_index()


class TestAuthDispatch:
    @pytest.mark.asyncio
    async def test_raises_when_no_credentials(self) -> None:
        with patch(
            "github.clients.client_factory._config",
            return_value={"github_host": "https://api.github.com"},
        ):
            with pytest.raises(MissingCredentials):
                await _list_auth_scopes()


class TestPersonalTokenAuthenticator:
    @pytest.mark.asyncio
    async def test_list_scopes_returns_single_generic_scope(self) -> None:
        scopes = await PersonalTokenAuthenticator.list_scopes(PAT_CONFIG)

        assert len(scopes) == 1
        assert scopes[0].organization is None
        assert isinstance(scopes[0].authenticator, PersonalTokenAuthenticator)

    def test_for_org_ignores_org(self) -> None:
        a = PersonalTokenAuthenticator.for_org(PAT_CONFIG, "org-a")
        b = PersonalTokenAuthenticator.for_org(PAT_CONFIG, "org-b")
        assert a is b


class TestGitHubAppAuthenticator:
    @pytest.mark.asyncio
    async def test_list_scopes_uses_configured_installation(self) -> None:
        config = {
            **APP_CONFIG,
            "github_app_installation_id": "123",
            "github_organization": "my-org",
        }
        scopes = await GitHubAppAuthenticator.list_scopes(config)

        assert len(scopes) == 1
        assert scopes[0].installation_id == "123"
        assert scopes[0].organization == "my-org"

    @pytest.mark.asyncio
    async def test_list_scopes_resolves_org_from_installation_id(self) -> None:
        config = {**APP_CONFIG, "github_app_installation_id": "123"}
        installation = {
            "id": 123,
            "account": {"login": "resolved-org", "type": "Organization"},
        }

        with patch.object(
            GitHubAppAuthenticator,
            "fetch_installation",
            AsyncMock(return_value=installation),
        ):
            scopes = await GitHubAppAuthenticator.list_scopes(config)

        assert len(scopes) == 1
        assert scopes[0].organization == "resolved-org"
        assert scopes[0].account_type == "Organization"
        assert scopes[0].installation_id == "123"

    @pytest.mark.asyncio
    async def test_list_scopes_discovers_installations(self) -> None:
        installation_page = [
            {
                "id": 1,
                "account": {"login": "org-a", "type": "Organization"},
            },
            {
                "id": 2,
                "account": {"login": "org-b", "type": "Organization"},
            },
        ]
        index = {
            "org-a": GitHubAppAuthenticator._scope_from_installation(
                APP_CONFIG, installation_page[0]
            ),
            "org-b": GitHubAppAuthenticator._scope_from_installation(
                APP_CONFIG, installation_page[1]
            ),
        }

        with patch.object(
            GitHubAppAuthenticator,
            "_ensure_index",
            AsyncMock(return_value=index),
        ):
            scopes = await GitHubAppAuthenticator.list_scopes(APP_CONFIG)

        assert {scope.organization for scope in scopes} == {"org-a", "org-b"}
