import asyncio
from typing import Any, Optional

from loguru import logger

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)
from github.clients.auth.github_app_jwt_client import (
    GitHubAppJwtClient,
    generate_app_jwt,
)
from github.helpers.exceptions import AuthenticationException
from port_ocean.utils.cache import cache_coroutine_result


class GitHubAppAuthenticator(AbstractGitHubAuthenticator):
    """Installation-bound GitHub App auth. installation_id is always required."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        github_host: str,
        organization: Optional[str] = None,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.organization = organization
        self.github_host = github_host.rstrip("/")
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    @property
    def rate_limit_scope(self) -> str:
        return f"installation:{self.installation_id}"

    async def get_token(self, **kwargs: Any) -> GitHubToken:
        if kwargs.get("return_jwt", False):
            return generate_app_jwt(self.app_id, self.private_key)

        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            jwt_token = generate_app_jwt(self.app_id, self.private_key)
            self.cached_installation_token = await self._fetch_installation_token(
                jwt_token.token
            )
            logger.info("New GitHub App token acquired.")
            return self.cached_installation_token

    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        token_response = await self.get_token(**kwargs)
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _fetch_installation_token(self, jwt_token: str) -> GitHubToken:
        try:
            url = f"{self.github_host}/app/installations/{self.installation_id}/access_tokens"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return GitHubToken(token=data["token"], expires_at=data["expires_at"])
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation token: {e}"
            ) from e

    @cache_coroutine_result()
    async def get_authenticated_actor(self) -> str:  # type: ignore[override]
        jwt_client = GitHubAppJwtClient(self.app_id, self.private_key, self.github_host)
        return await jwt_client.get_authenticated_actor()
