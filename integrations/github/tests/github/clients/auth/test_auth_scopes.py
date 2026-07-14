from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from github.clients.auth.auth_backend import (
    AppAuthBackend,
    PatAuthBackend,
    get_authenticator_for_organization,
    get_integration_actor,
    list_authenticators,
    resolve_auth_backend,
)
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.github_app import installation_registry
from github.clients.auth.github_app.installation_registry import (
    reset_authenticators_by_org,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.helpers.exceptions import AuthenticationException, MissingCredentials
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


@contextmanager
def _integration_config(
    config: dict[str, Any], overrides: dict[str, Any] | None = None
) -> Iterator[None]:
    target = ocean.integration_config
    saved = dict(target)
    try:
        target.clear()
        target.update({**config, **(overrides or {})})
        yield
    finally:
        target.clear()
        target.update(saved)


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
                resolve_auth_backend()
            with pytest.raises(MissingCredentials):
                await list_authenticators()
        finally:
            config.clear()
            config.update(saved)

    def test_prefers_pat_when_both_configured(self) -> None:
        with _integration_config(PAT_CONFIG):
            assert resolve_auth_backend() is PatAuthBackend

    def test_resolves_app_backend(self) -> None:
        with _integration_config(APP_CONFIG):
            assert resolve_auth_backend() is AppAuthBackend

    @pytest.mark.asyncio
    async def test_get_integration_actor_uses_app_authenticator(self) -> None:
        with _integration_config(APP_CONFIG):
            with patch.object(
                GitHubAppAuthenticator,
                "get_authenticated_actor",
                AsyncMock(return_value="my-app[bot]"),
            ) as mock_actor:
                actor = await get_integration_actor()

            assert actor == "my-app[bot]"
            mock_actor.assert_awaited_once()


class TestPersonalTokenAuthenticator:
    @pytest.mark.asyncio
    async def test_list_authenticators_returns_single_pat_authenticator(self) -> None:
        with _integration_config(PAT_CONFIG):
            authenticators = await PatAuthBackend.list_authenticators()

        assert len(authenticators) == 1
        assert isinstance(authenticators[0], PersonalTokenAuthenticator)

    @pytest.mark.asyncio
    async def test_get_authenticator_for_organization_ignores_org(self) -> None:
        with _integration_config(PAT_CONFIG):
            a = await PatAuthBackend.get_authenticator_for_organization("org-a")
            b = await PatAuthBackend.get_authenticator_for_organization("org-b")
        assert a is b


class TestInstallationRegistry:
    @pytest.mark.asyncio
    async def test_list_authenticators_discovers_all_installations(self) -> None:
        async def _installations() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "id": 1,
                    "account": {"login": "org-a", "type": "Organization"},
                },
                {
                    "id": 2,
                    "account": {"login": "org-b", "type": "Organization"},
                },
            ]

        with _integration_config(
            APP_CONFIG,
            {
                "github_app_installation_id": "999",
                "github_organization": "ignored-org",
            },
        ):
            with patch.object(
                GitHubAppAuthenticator,
                "iter_app_installations",
                return_value=_installations(),
            ) as mock_iter:
                authenticators = await AppAuthBackend.list_authenticators()

            mock_iter.assert_called_once()
            assert len(authenticators) == 2
            assert {
                auth.installation_id
                for auth in authenticators
                if isinstance(auth, GitHubAppInstallationAuthenticator)
            } == {"1", "2"}

    @pytest.mark.asyncio
    async def test_list_authenticators_discovers_installations(self) -> None:
        with _integration_config(APP_CONFIG):
            index = {
                "org-a": installation_registry._authenticator(
                    installation_id="1"
                ),
                "org-b": installation_registry._authenticator(
                    installation_id="2"
                ),
            }

            with patch.object(
                installation_registry,
                "_discover_authenticators",
                AsyncMock(return_value=index),
            ):
                authenticators = await AppAuthBackend.list_authenticators()

            assert len(authenticators) == 2
            assert {
                auth.installation_id
                for auth in authenticators
                if isinstance(auth, GitHubAppInstallationAuthenticator)
            } == {"1", "2"}

    @pytest.mark.asyncio
    async def test_get_authenticator_for_organization_discovers_on_demand(
        self,
    ) -> None:
        async def _installations() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "id": 123,
                    "account": {"login": "my-org", "type": "Organization"},
                }
            ]

        with _integration_config(
            APP_CONFIG,
            {
                "github_app_installation_id": "999",
                "github_organization": "ignored-org",
            },
        ):
            with patch.object(
                GitHubAppAuthenticator,
                "iter_app_installations",
                return_value=_installations(),
            ):
                resolved = await get_authenticator_for_organization("my-org")

        assert isinstance(resolved, GitHubAppInstallationAuthenticator)
        assert resolved.installation_id == "123"

    @pytest.mark.asyncio
    async def test_get_authenticator_for_organization_returns_indexed_authenticator(
        self,
    ) -> None:
        with _integration_config(APP_CONFIG):
            auth = installation_registry._authenticator(installation_id="123")
            installation_registry._authenticators_by_org = {"my-org": auth}

            resolved = await AppAuthBackend.get_authenticator_for_organization(
                "my-org"
            )

        assert isinstance(resolved, GitHubAppInstallationAuthenticator)
        assert resolved.installation_id == "123"

    @pytest.mark.asyncio
    async def test_get_authenticator_for_organization_raises_for_unknown_org(
        self,
    ) -> None:
        with _integration_config(APP_CONFIG):
            installation_registry._authenticators_by_org = {}

            with pytest.raises(AuthenticationException, match="my-org"):
                await AppAuthBackend.get_authenticator_for_organization("my-org")
