from typing import Any
from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubToken,
    GitHubHeaders,
)
from loguru import logger


class PersonalTokenAuthenticator(AbstractGitHubAuthenticator):
    def __init__(self, token: str):
        self._token = GitHubToken(token=token)

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
