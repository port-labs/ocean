import hashlib

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_coroutine_result

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)


def _token_rate_limit_scope(token: str) -> str:
    """Scope limiters per credential so identity-propagated user tokens do not share
    one `pat` bucket with each other or with the integration PAT.
    """
    digest = hashlib.sha256(token.encode()).hexdigest()[:16]
    return f"pat:{digest}"


class PersonalTokenAuthenticator(AbstractGitHubAuthenticator):
    def __init__(self, token: str, organization: str | None = None):
        self._token = GitHubToken(token=token)
        self.organization = organization
        self._rate_limit_scope = _token_rate_limit_scope(token)

    @property
    def rate_limit_scope(self) -> str:
        return self._rate_limit_scope

    @classmethod
    def from_config(cls) -> "PersonalTokenAuthenticator":
        return cls(
            ocean.integration_config["github_token"],
            ocean.integration_config.get("github_organization"),
        )

    async def get_token(self) -> GitHubToken:
        logger.info("Using personal access token.")
        return self._token

    async def get_headers(self) -> GitHubHeaders:
        token_response = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def get_authenticated_actor(self) -> str:
        return await self._fetch_authenticated_actor()

    @cache_coroutine_result()
    async def _fetch_authenticated_actor(self) -> str:
        github_host = ocean.integration_config["github_host"]
        response = await self.client.get(
            f"{github_host}/user",
            headers=(await self.get_headers()).as_dict(),
        )
        response.raise_for_status()
        return response.json()["login"]
