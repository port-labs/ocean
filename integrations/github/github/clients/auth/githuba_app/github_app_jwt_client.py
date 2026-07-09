import base64
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Optional

import jwt

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)
from github.helpers.exceptions import AuthenticationException
from port_ocean.utils.cache import cache_coroutine_result

JWT_EXPIRY_MINUTES = 10
INSTALLATIONS_PAGE_SIZE = 100


def generate_app_jwt(app_id: str, private_key: str) -> GitHubToken:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload = {
        "iss": app_id,
        "iat": now,
        "exp": expires_at,
    }
    if private_key.startswith("-----BEGIN"):
        decoded_private_key = private_key
    else:
        decoded_private_key = base64.b64decode(private_key).decode()

    token = jwt.encode(payload, decoded_private_key, algorithm="RS256")
    return GitHubToken(token=token, expires_at=str(int(expires_at.timestamp())))


class GitHubAppJwtClient(AbstractGitHubAuthenticator):
    """App-level JWT auth for discovery and GET /app. Not installation-scoped."""

    def __init__(self, app_id: str, private_key: str, github_host: str):
        self.app_id = app_id
        self.private_key = private_key
        self.github_host = github_host.rstrip("/")

    @property
    def rate_limit_scope(self) -> str:
        return f"app:{self.app_id}"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "GitHubAppJwtClient":
        return cls(
            app_id=config["github_app_id"],
            private_key=config["github_app_private_key"],
            github_host=config["github_host"],
        )

    async def get_token(self, **kwargs: Any) -> GitHubToken:
        return generate_app_jwt(self.app_id, self.private_key)

    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        token = await self.get_token(**kwargs)
        return GitHubHeaders(
            Authorization=f"Bearer {token.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _jwt_headers(self) -> dict[str, str]:
        return (await self.get_headers()).as_dict()

    def _parse_next_link(self, link_header: str) -> Optional[str]:
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return None

    async def fetch_installation(self, installation_id: str) -> dict[str, Any]:
        url = f"{self.github_host}/app/installations/{installation_id}"
        response = await self.client.get(url, headers=await self._jwt_headers())
        response.raise_for_status()
        return response.json()

    async def iter_app_installations(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url: Optional[str] = f"{self.github_host}/app/installations"
        headers = await self._jwt_headers()

        while url:
            response = await self.client.get(
                url,
                params={"per_page": INSTALLATIONS_PAGE_SIZE},
                headers=headers,
            )
            response.raise_for_status()
            page: list[dict[str, Any]] = response.json()
            if page:
                yield page
            link_header = response.headers.get("Link", "")
            url = self._parse_next_link(link_header)

    async def get_app(self) -> dict[str, Any]:
        response = await self.client.get(
            f"{self.github_host}/app", headers=await self._jwt_headers()
        )
        response.raise_for_status()
        return response.json()

    @cache_coroutine_result()
    async def get_authenticated_actor(self) -> str:
        app = await self.get_app()
        return f"{app['slug']}[bot]"
