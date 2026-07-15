import asyncio
from typing import Optional

from loguru import logger

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.helpers.exceptions import AuthenticationException


class GitHubAppInstallationAuthenticator(AbstractGitHubAuthenticator):
    """Installation-bound GitHub App auth. installation_id is always required."""

    def __init__(
        self,
        app_auth: GitHubAppAuthenticator,
        installation_id: str,
    ):
        self.app_auth = app_auth
        self.installation_id = installation_id
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    @property
    def rate_limit_scope(self) -> str:
        return f"installation:{self.installation_id}"

    async def get_token(self) -> GitHubToken:
        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            app_token = await self.app_auth.get_token()
            self.cached_installation_token = await self._fetch_installation_token(
                app_token.token
            )
            logger.info("New GitHub App token acquired.")
            return self.cached_installation_token

    async def get_headers(self) -> GitHubHeaders:
        token_response = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _fetch_installation_token(self, app_token: str) -> GitHubToken:
        try:
            url = f"{self.app_auth.github_host}/app/installations/{self.installation_id}/access_tokens"
            headers = {"Authorization": f"Bearer {app_token}"}
            response = await self.client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return GitHubToken(token=data["token"], expires_at=data["expires_at"])
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation token: {e}"
            ) from e
