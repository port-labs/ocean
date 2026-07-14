from abc import ABC, abstractmethod
from typing import Any, Sequence

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_registry import (
    GitHubAppInstallationRegistry,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.helpers.exceptions import MissingCredentials


class GitHubAuthBackend(ABC):
    @classmethod
    @abstractmethod
    def matches(cls, config: dict[str, Any]) -> bool:
        pass

    @classmethod
    @abstractmethod
    async def list_authenticators(
        cls, config: dict[str, Any]
    ) -> Sequence[AbstractGitHubAuthenticator]:
        pass

    @classmethod
    @abstractmethod
    def get_authenticator_for_organization(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        pass


class PatAuthBackend(GitHubAuthBackend):
    @classmethod
    def matches(cls, config: dict[str, Any]) -> bool:
        return bool(config.get("github_token"))

    @classmethod
    async def list_authenticators(
        cls, config: dict[str, Any]
    ) -> Sequence[AbstractGitHubAuthenticator]:
        return await PersonalTokenAuthenticator.list_authenticators(config)

    @classmethod
    def get_authenticator_for_organization(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        return PersonalTokenAuthenticator.get_authenticator_for_organization(
            config, organization
        )


class AppAuthBackend(GitHubAuthBackend):
    @classmethod
    def matches(cls, config: dict[str, Any]) -> bool:
        return bool(
            config.get("github_app_id") and config.get("github_app_private_key")
        )

    @classmethod
    async def list_authenticators(
        cls, config: dict[str, Any]
    ) -> Sequence[AbstractGitHubAuthenticator]:
        return await GitHubAppInstallationRegistry.list_authenticators(config)

    @classmethod
    def get_authenticator_for_organization(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        if organization is None:
            raise MissingCredentials(
                "Organization is required for GitHub App authentication."
            )
        return GitHubAppInstallationRegistry.get_authenticator_for_organization(
            config, organization
        )


_BACKENDS: tuple[type[GitHubAuthBackend], ...] = (PatAuthBackend, AppAuthBackend)


def resolve_auth_backend(config: dict[str, Any]) -> type[GitHubAuthBackend]:
    for backend in _BACKENDS:
        if backend.matches(config):
            return backend
    raise MissingCredentials("No valid GitHub credentials provided.")


async def list_authenticators(
    config: dict[str, Any],
) -> Sequence[AbstractGitHubAuthenticator]:
    backend = resolve_auth_backend(config)
    return await backend.list_authenticators(config)


def get_authenticator_for_organization(
    config: dict[str, Any], organization: str | None
) -> AbstractGitHubAuthenticator:
    backend = resolve_auth_backend(config)
    return backend.get_authenticator_for_organization(config, organization)


async def get_integration_actor(config: dict[str, Any]) -> str:
    backend = resolve_auth_backend(config)
    if backend is PatAuthBackend:
        authenticator = PersonalTokenAuthenticator.get_authenticator_for_organization(
            config, None
        )
        return await authenticator.get_authenticated_actor()
    return await GitHubAppAuthenticator.from_config(config).get_authenticated_actor()
