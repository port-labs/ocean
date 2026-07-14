from unittest.mock import AsyncMock, patch

import pytest

from github.clients.auth.auth_backend import (
    AppAuthBackend,
    PatAuthBackend,
    resolve_auth_backend,
)
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.github_app.installation_registry import (
    GitHubAppInstallationRegistry,
    reset_installation_index,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.client_factory import _list_auth_scopes
from github.helpers.exceptions import MissingCredentials
from port_ocean.context.ocean import ocean

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


class TestAuthBackendResolution:
    @pytest.mark.asyncio
    async def test_raises_when_no_credentials(self) -> None:
        config = ocean.integration_config
        saved = dict(config)
        try:
            config.clear()
            config["github_host"] = "https://api.github.com"
            with pytest.raises(MissingCredentials):
                resolve_auth_backend(config)
            with pytest.raises(MissingCredentials):
                await _list_auth_scopes()
        finally:
            config.clear()
            config.update(saved)

    def test_prefers_pat_when_both_configured(self) -> None:
        assert resolve_auth_backend(PAT_CONFIG) is PatAuthBackend

    def test_resolves_app_backend(self) -> None:
        assert resolve_auth_backend(APP_CONFIG) is AppAuthBackend

    def test_app_for_actor_uses_app_authenticator(self) -> None:
        auth = AppAuthBackend.for_actor(APP_CONFIG)
        assert isinstance(auth, GitHubAppAuthenticator)


class TestPersonalTokenAuthenticator:
    @pytest.mark.asyncio
    async def test_list_scopes_returns_single_generic_scope(self) -> None:
        scopes = await PatAuthBackend.list_scopes(PAT_CONFIG)

        assert len(scopes) == 1
        assert scopes[0].organization is None
        assert isinstance(scopes[0].authenticator, PersonalTokenAuthenticator)

    def test_for_org_ignores_org(self) -> None:
        a = PatAuthBackend.for_org(PAT_CONFIG, "org-a")
        b = PatAuthBackend.for_org(PAT_CONFIG, "org-b")
        assert a is b


class TestGitHubAppInstallationRegistry:
    @pytest.mark.asyncio
    async def test_list_scopes_uses_configured_installation(self) -> None:
        config = {
            **APP_CONFIG,
            "github_app_installation_id": "123",
            "github_organization": "my-org",
        }
        scopes = await AppAuthBackend.list_scopes(config)

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
            scopes = await AppAuthBackend.list_scopes(config)

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
            "org-a": GitHubAppInstallationRegistry._scope_from_installation(
                APP_CONFIG, installation_page[0]
            ),
            "org-b": GitHubAppInstallationRegistry._scope_from_installation(
                APP_CONFIG, installation_page[1]
            ),
        }

        with patch.object(
            GitHubAppInstallationRegistry,
            "_ensure_index",
            AsyncMock(return_value=index),
        ):
            scopes = await AppAuthBackend.list_scopes(APP_CONFIG)

        assert {scope.organization for scope in scopes} == {"org-a", "org-b"}

    def test_for_org_returns_indexed_authenticator(self) -> None:
        import github.clients.auth.github_app.installation_registry as registry

        config = {
            **APP_CONFIG,
            "github_app_installation_id": "123",
            "github_organization": "my-org",
        }
        scope = GitHubAppInstallationRegistry._scope_from_installation(
            config,
            {"id": 123, "account": {"login": "my-org", "type": "Organization"}},
        )
        registry._scopes_by_org = {"my-org": scope}

        auth = AppAuthBackend.for_org(config, "my-org")
        assert isinstance(auth, GitHubAppInstallationAuthenticator)
        assert auth.installation_id == "123"
        assert auth.organization == "my-org"
