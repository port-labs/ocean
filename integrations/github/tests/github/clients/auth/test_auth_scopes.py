from unittest.mock import AsyncMock, patch

import pytest

from github.clients.auth.auth_backend import (
    AppAuthBackend,
    PatAuthBackend,
    get_integration_actor,
    list_authenticators,
    resolve_auth_backend,
)
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.github_app.installation_registry import (
    GitHubAppInstallationRegistry,
    reset_authenticators_by_org,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
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
    reset_authenticators_by_org()


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
                await list_authenticators(config)
        finally:
            config.clear()
            config.update(saved)

    def test_prefers_pat_when_both_configured(self) -> None:
        assert resolve_auth_backend(PAT_CONFIG) is PatAuthBackend

    def test_resolves_app_backend(self) -> None:
        assert resolve_auth_backend(APP_CONFIG) is AppAuthBackend

    @pytest.mark.asyncio
    async def test_get_integration_actor_uses_app_authenticator(self) -> None:
        with patch.object(
            GitHubAppAuthenticator,
            "get_authenticated_actor",
            AsyncMock(return_value="my-app[bot]"),
        ) as mock_actor:
            actor = await get_integration_actor(APP_CONFIG)

        assert actor == "my-app[bot]"
        mock_actor.assert_awaited_once()


class TestPersonalTokenAuthenticator:
    @pytest.mark.asyncio
    async def test_list_authenticators_returns_single_pat_authenticator(self) -> None:
        authenticators = await PatAuthBackend.list_authenticators(PAT_CONFIG)

        assert len(authenticators) == 1
        assert isinstance(authenticators[0], PersonalTokenAuthenticator)

    def test_get_authenticator_for_organization_ignores_org(self) -> None:
        a = PatAuthBackend.get_authenticator_for_organization(PAT_CONFIG, "org-a")
        b = PatAuthBackend.get_authenticator_for_organization(PAT_CONFIG, "org-b")
        assert a is b


class TestGitHubAppInstallationRegistry:
    @pytest.mark.asyncio
    async def test_list_authenticators_uses_configured_installation(self) -> None:
        config = {
            **APP_CONFIG,
            "github_app_installation_id": "123",
            "github_organization": "my-org",
        }
        authenticators = await AppAuthBackend.list_authenticators(config)

        assert len(authenticators) == 1
        auth = authenticators[0]
        assert isinstance(auth, GitHubAppInstallationAuthenticator)
        assert auth.installation_id == "123"

    @pytest.mark.asyncio
    async def test_list_authenticators_resolves_org_from_installation_id(self) -> None:
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
            authenticators = await AppAuthBackend.list_authenticators(config)

        assert len(authenticators) == 1
        auth = authenticators[0]
        assert isinstance(auth, GitHubAppInstallationAuthenticator)
        assert auth.installation_id == "123"

    @pytest.mark.asyncio
    async def test_list_authenticators_discovers_installations(self) -> None:
        index = {
            "org-a": GitHubAppInstallationRegistry._authenticator(
                APP_CONFIG, installation_id="1"
            ),
            "org-b": GitHubAppInstallationRegistry._authenticator(
                APP_CONFIG, installation_id="2"
            ),
        }

        with patch.object(
            GitHubAppInstallationRegistry,
            "_get_authenticators_by_org",
            AsyncMock(return_value=index),
        ):
            authenticators = await AppAuthBackend.list_authenticators(APP_CONFIG)

        assert len(authenticators) == 2
        assert {
            auth.installation_id
            for auth in authenticators
            if isinstance(auth, GitHubAppInstallationAuthenticator)
        } == {"1", "2"}

    def test_get_authenticator_for_organization_returns_indexed_authenticator(
        self,
    ) -> None:
        import github.clients.auth.github_app.installation_registry as registry

        config = {
            **APP_CONFIG,
            "github_app_installation_id": "123",
            "github_organization": "my-org",
        }
        auth = GitHubAppInstallationRegistry._authenticator(
            config, installation_id="123"
        )
        registry._authenticators_by_org = {"my-org": auth}

        resolved = AppAuthBackend.get_authenticator_for_organization(config, "my-org")
        assert isinstance(resolved, GitHubAppInstallationAuthenticator)
        assert resolved.installation_id == "123"
