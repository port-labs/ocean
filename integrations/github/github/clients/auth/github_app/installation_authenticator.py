import asyncio
from typing import Optional
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)


class GitHubAppInstallationAuthenticator(AbstractGitHubAuthenticator):
    """GitHub App auth bound to an organization."""

    def __init__(
        self,
        app_auth: GitHubAppAuthenticator,
        organization: str,
        installation_id: str,
    ):
        self.app_auth = app_auth
        self.organization: str = organization
        self.installation_id = installation_id
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    @property
    def rate_limit_scope(self) -> str:
        return f"installation:{self.installation_id}"

    async def get_headers(self) -> GitHubHeaders:
        token_response = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def get_token(self) -> GitHubToken:
        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            self.cached_installation_token = (
                await self.app_auth.fetch_installation_access_token(
                    self.installation_id
                )
            )
            return self.cached_installation_token
