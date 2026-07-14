import base64
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Optional

import jwt
from port_ocean.utils.cache import cache_coroutine_result, cache_iterator_result

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubHeaders,
    GitHubToken,
)


class GitHubAppAuthenticator(AbstractGitHubAuthenticator):
    """App-level JWT auth for discovery and GET /app. Not installation-scoped."""

    _JWT_EXPIRY_MINUTES = 10
    _INSTALLATIONS_PAGE_SIZE = 100

    def __init__(self, app_id: str, private_key: str, github_host: str):
        self.app_id = app_id
        self.private_key = private_key
        self.github_host = github_host.rstrip("/")

    @property
    def rate_limit_scope(self) -> str:
        return f"app:{self.app_id}"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "GitHubAppAuthenticator":
        return cls(
            app_id=config["github_app_id"],
            private_key=config["github_app_private_key"],
            github_host=config["github_host"],
        )

    def _generate_jwt(self) -> GitHubToken:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self._JWT_EXPIRY_MINUTES)
        payload = {
            "iss": self.app_id,
            "iat": now,
            "exp": expires_at,
        }
        if self.private_key.startswith("-----BEGIN"):
            decoded_private_key = self.private_key
        else:
            decoded_private_key = base64.b64decode(self.private_key).decode()

        token = jwt.encode(payload, decoded_private_key, algorithm="RS256")
        return GitHubToken(token=token, expires_at=str(int(expires_at.timestamp())))

    async def get_token(self) -> GitHubToken:
        return self._generate_jwt()

    async def get_headers(self) -> GitHubHeaders:
        token = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    def _parse_next_link(self, link_header: str) -> Optional[str]:
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return None

    async def fetch_installation(self, installation_id: str) -> dict[str, Any]:
        url = f"{self.github_host}/app/installations/{installation_id}"
        response = await self.client.get(
            url, headers=(await self.get_headers()).as_dict()
        )
        response.raise_for_status()
        return response.json()

    @cache_iterator_result()
    async def iter_app_installations(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url: Optional[str] = f"{self.github_host}/app/installations"
        headers = (await self.get_headers()).as_dict()

        while url:
            response = await self.client.get(
                url,
                params={"per_page": self._INSTALLATIONS_PAGE_SIZE},
                headers=headers,
            )
            response.raise_for_status()
            page: list[dict[str, Any]] = response.json()
            if page:
                yield page
            link_header = response.headers.get("Link", "")
            url = self._parse_next_link(link_header)

    @cache_coroutine_result()
    async def get_authenticated_actor(self) -> str:  # type: ignore[override]
        response = await self.client.get(
            f"{self.github_host}/app",
            headers=(await self.get_headers()).as_dict(),
        )
        response.raise_for_status()
        app = response.json()

        return f"{app['slug']}[bot]"
