from abc import ABC, abstractmethod
from typing import Any

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    AuthScope,
)
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
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        pass

    @classmethod
    @abstractmethod
    def for_org(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        pass

    @classmethod
    @abstractmethod
    def for_actor(cls, config: dict[str, Any]) -> AbstractGitHubAuthenticator:
        pass


class PatAuthBackend(GitHubAuthBackend):
    @classmethod
    def matches(cls, config: dict[str, Any]) -> bool:
        return bool(config.get("github_token"))

    @classmethod
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        return await PersonalTokenAuthenticator.list_scopes(config)

    @classmethod
    def for_org(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        return PersonalTokenAuthenticator.for_org(config, organization)

    @classmethod
    def for_actor(cls, config: dict[str, Any]) -> AbstractGitHubAuthenticator:
        return PersonalTokenAuthenticator.for_org(config, None)


class AppAuthBackend(GitHubAuthBackend):
    @classmethod
    def matches(cls, config: dict[str, Any]) -> bool:
        return bool(
            config.get("github_app_id") and config.get("github_app_private_key")
        )

    @classmethod
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        return await GitHubAppInstallationRegistry.list_scopes(config)

    @classmethod
    def for_org(
        cls, config: dict[str, Any], organization: str | None
    ) -> AbstractGitHubAuthenticator:
        if organization is None:
            raise MissingCredentials(
                "Organization is required for GitHub App authentication."
            )
        return GitHubAppInstallationRegistry.for_org(config, organization)

    @classmethod
    def for_actor(cls, config: dict[str, Any]) -> AbstractGitHubAuthenticator:
        return GitHubAppAuthenticator.from_config(config)


_BACKENDS: tuple[type[GitHubAuthBackend], ...] = (PatAuthBackend, AppAuthBackend)


def resolve_auth_backend(config: dict[str, Any]) -> type[GitHubAuthBackend]:
    for backend in _BACKENDS:
        if backend.matches(config):
            return backend
    raise MissingCredentials("No valid GitHub credentials provided.")
