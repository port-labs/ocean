from abc import ABC, abstractmethod
from typing import Sequence

from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_registry import (
    get_installation_authenticator_for_organization,
    list_installations_authenticators,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.helpers.exceptions import MissingCredentials


class _GitHubAuthProvider(ABC):
    @classmethod
    @abstractmethod
    def matches(cls) -> bool:
        pass

    @classmethod
    @abstractmethod
    async def list_authenticators(cls) -> Sequence[AbstractGitHubAuthenticator]:
        pass

    @classmethod
    @abstractmethod
    async def get_authenticator_for_organization(
        cls, organization: str
    ) -> AbstractGitHubAuthenticator:
        pass

    @classmethod
    @abstractmethod
    async def get_integration_actor(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def is_app_auth(cls) -> bool:
        pass


class _PatAuthProvider(_GitHubAuthProvider):
    @classmethod
    def _authenticator(cls) -> PersonalTokenAuthenticator:
        return PersonalTokenAuthenticator.from_config()

    @classmethod
    def matches(cls) -> bool:
        return bool(ocean.integration_config.get("github_token"))

    @classmethod
    async def list_authenticators(cls) -> Sequence[AbstractGitHubAuthenticator]:
        return [cls._authenticator()]

    @classmethod
    async def get_authenticator_for_organization(
        cls, organization: str
    ) -> AbstractGitHubAuthenticator:
        return cls._authenticator()

    @classmethod
    async def get_integration_actor(cls) -> str:
        return await cls._authenticator().get_authenticated_actor()

    @classmethod
    def is_app_auth(cls) -> bool:
        return False


class _AppAuthProvider(_GitHubAuthProvider):
    @classmethod
    def matches(cls) -> bool:
        config = ocean.integration_config
        return bool(
            config.get("github_app_id") and config.get("github_app_private_key")
        )

    @classmethod
    async def list_authenticators(cls) -> Sequence[AbstractGitHubAuthenticator]:
        return await list_installations_authenticators()

    @classmethod
    async def get_authenticator_for_organization(
        cls, organization: str
    ) -> AbstractGitHubAuthenticator:
        return await get_installation_authenticator_for_organization(organization)

    @classmethod
    async def get_integration_actor(cls) -> str:
        return await GitHubAppAuthenticator.from_config().get_authenticated_actor()

    @classmethod
    def is_app_auth(cls) -> bool:
        return True


_providers: tuple[type[_GitHubAuthProvider], ...] = (
    _PatAuthProvider,
    _AppAuthProvider,
)


def _resolve_provider() -> type[_GitHubAuthProvider]:
    for provider in _providers:
        if provider.matches():
            return provider
    raise MissingCredentials("No valid GitHub credentials provided.")


def get_auth_provider() -> type[_GitHubAuthProvider]:
    return _resolve_provider()
