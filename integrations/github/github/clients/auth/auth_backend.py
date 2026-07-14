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


class GitHubAuthBackend(ABC):
    @classmethod
    @abstractmethod
    def matches(cls) -> bool:
        pass

    @classmethod
    @abstractmethod
    async def list_authenticators(cls) -> list[AbstractGitHubAuthenticator]:
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


class PatAuthBackend(GitHubAuthBackend):
    @classmethod
    def _authenticator(cls) -> PersonalTokenAuthenticator:
        return PersonalTokenAuthenticator.from_config()

    @classmethod
    def matches(cls) -> bool:
        return bool(ocean.integration_config.get("github_token"))

    @classmethod
    async def list_authenticators(cls) -> list[AbstractGitHubAuthenticator]:
        return [cls._authenticator()]

    @classmethod
    async def get_authenticator_for_organization(
        cls, organization: str
    ) -> AbstractGitHubAuthenticator:
        return cls._authenticator()

    @classmethod
    async def get_integration_actor(cls) -> str:
        return await cls._authenticator().get_authenticated_actor()


class AppAuthBackend(GitHubAuthBackend):
    @classmethod
    def matches(cls) -> bool:
        config = ocean.integration_config
        return bool(
            config.get("github_app_id") and config.get("github_app_private_key")
        )

    @classmethod
    async def list_authenticators(cls) -> list[AbstractGitHubAuthenticator]:
        return await list_installations_authenticators()

    @classmethod
    async def get_authenticator_for_organization(
        cls, organization: str
    ) -> AbstractGitHubAuthenticator:
        return await get_installation_authenticator_for_organization(organization)

    @classmethod
    async def get_integration_actor(cls) -> str:
        return await GitHubAppAuthenticator.from_config().get_authenticated_actor()


_BACKENDS: tuple[type[GitHubAuthBackend], ...] = (PatAuthBackend, AppAuthBackend)


def resolve_auth_backend() -> type[GitHubAuthBackend]:
    for backend in _BACKENDS:
        if backend.matches():
            return backend
    raise MissingCredentials("No valid GitHub credentials provided.")


async def list_authenticators() -> list[AbstractGitHubAuthenticator]:
    backend = resolve_auth_backend()
    return await backend.list_authenticators()


async def get_authenticator_for_organization(
    organization: str,
) -> AbstractGitHubAuthenticator:
    backend = resolve_auth_backend()
    return await backend.get_authenticator_for_organization(organization)


async def get_integration_actor() -> str:
    backend = resolve_auth_backend()
    return await backend.get_integration_actor()
