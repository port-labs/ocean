import asyncio
import base64
from typing import Any, AsyncIterator, Optional, Dict, List
from loguru import logger
from datetime import datetime, timedelta, timezone
import jwt
from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    GitHubToken,
    GitHubHeaders,
)
from github.helpers.exceptions import AuthenticationException


class GitHubAppAuthenticator(AbstractGitHubAuthenticator):
    JWT_EXPIRY_MINUTES = 10
    INSTALLATIONS_PAGE_SIZE = 100

    def __init__(
        self,
        app_id: str,
        private_key: str,
        github_host: str,
        organization: Optional[str] = None,
        installation_id: Optional[str] = None,
    ):
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key = private_key
        self.organization = organization
        self.github_host = github_host.rstrip("/")
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    async def get_token(self, **kwargs: Any) -> GitHubToken:
        jwt_token = self._generate_jwt()
        if kwargs.get("return_jwt", False):
            return jwt_token

        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            if not self.installation_id:
                self.installation_id = await self._fetch_installation_id(
                    jwt_token.token
                )

            self.cached_installation_token = await self._fetch_installation_token(
                jwt_token.token
            )
            logger.info("New GitHub App token acquired.")
            return self.cached_installation_token

    async def get_headers(self, token: str) -> GitHubHeaders:
        return GitHubHeaders(
            Authorization=f"Bearer {token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def list_installations(self) -> AsyncIterator[List[Dict[str, Any]]]:
        """Yield pages of app installations using JWT auth.

        Each installation dict contains at minimum ``id``, ``account.login``,
        and ``account.type``.  Requires only the app credentials (no org /
        installation token needed).
        """
        jwt_token = self._generate_jwt()
        headers = await self.get_headers(jwt_token.token)
        url = f"{self.github_host}/app/installations"

        while url:
            response = await self.client.get(
                url, params={"per_page": self.INSTALLATIONS_PAGE_SIZE}, headers=headers
            )
            response.raise_for_status()
            page: List[Dict[str, Any]] = response.json()
            if page:
                yield page
            link_header = response.headers.get("Link", "")
            url = _parse_next_link(link_header)

    async def _fetch_installation_id(self, jwt_token: str) -> str:
        try:
            url = f"{self.github_host}/users/{self.organization}/installation"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return str(response.json()["id"])
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation ID: {e}"
            ) from e

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

    def _generate_jwt(self) -> GitHubToken:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.JWT_EXPIRY_MINUTES)
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


def _parse_next_link(link_header: str) -> Optional[str]:
    """Extract the ``next`` URL from a GitHub ``Link`` response header."""
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            url_part = part.split(";")[0].strip()
            return url_part.strip("<>")
    return None
