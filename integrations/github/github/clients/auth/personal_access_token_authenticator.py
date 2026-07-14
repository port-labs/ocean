from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_coroutine_result

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
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
    def from_config(cls) -> "PersonalTokenAuthenticator":
        return cls(ocean.integration_config["github_token"])

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

    @cache_coroutine_result()
    async def get_authenticated_actor(self) -> str:
        github_host = ocean.integration_config["github_host"]
        response = await self.client.get(
            f"{github_host}/user",
            headers=(await self.get_headers()).as_dict(),
        )
        response.raise_for_status()
        return response.json()["login"]
