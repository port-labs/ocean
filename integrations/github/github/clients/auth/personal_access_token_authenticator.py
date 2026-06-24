from typing import Any

from loguru import logger

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    AuthScope,
    GitHubHeaders,
    GitHubToken,
)

_by_token: dict[str, "PersonalTokenAuthenticator"] = {}


def reset_pat_instances() -> None:
    global _by_token
    _by_token = {}


class PersonalTokenAuthenticator(AbstractGitHubAuthenticator):
    def __init__(self, token: str):
        self._token = GitHubToken(token=token)

    @property
    def rate_limit_scope(self) -> str:
        return "pat"

    @classmethod
    def _for_token(cls, token: str) -> "PersonalTokenAuthenticator":
        if token not in _by_token:
            _by_token[token] = cls(token)
        return _by_token[token]

    @classmethod
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        auth = cls._for_token(config["github_token"])
        return [AuthScope(None, None, None, auth)]

    @classmethod
    def for_org(
        cls, config: dict[str, Any], organization: str | None
    ) -> "PersonalTokenAuthenticator":
        return cls._for_token(config["github_token"])

    async def get_token(self, **kwargs: Any) -> GitHubToken:
        logger.info("Using personal access token.")
        return self._token

    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        token_response = await self.get_token(**kwargs)
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )
