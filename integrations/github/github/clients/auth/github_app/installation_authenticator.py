import asyncio
from typing import Optional
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)


class GitHubAppInstallationAuthenticator(AbstractGitHubAuthenticator):
    """GitHub App auth bound to an organization, with optional installation ID."""

    def __init__(
        self,
        app_auth: GitHubAppAuthenticator,
        organization: str,
        installation_id: Optional[str] = None,
    ):
        self.app_auth = app_auth
        self.organization = organization
        self.installation_id = installation_id
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    @property
    def rate_limit_scope(self) -> str:
        # TODO: replace to installation id based rate limit scope after create_github_client is deprecated
        return f"installation:{self.organization}"

    async def get_headers(self) -> GitHubHeaders:
        token_response = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _get_installation_id(self) -> str:
        if self.installation_id:
            return self.installation_id

        self.installation_id = await self.app_auth.get_installation_id_for_organization(
            self.organization
        )
        return self.installation_id

    async def get_token(self) -> GitHubToken:
        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            installation_id = await self._get_installation_id()
            self.cached_installation_token = (
                await self.app_auth.fetch_installation_access_token(installation_id)
            )
            return self.cached_installation_token
