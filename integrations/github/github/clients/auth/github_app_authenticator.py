import asyncio
import base64
from typing import Optional
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

    def __init__(
        self,
        app_id: str,
        private_key: str,
        organization: str,
        github_host: str,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.organization = organization
        self.github_host = github_host.rstrip("/")
        self.installation_id: Optional[int] = None
        self.cached_token: Optional[GitHubToken] = None
        self.lock = asyncio.Lock()

    async def get_token(self) -> GitHubToken:
        async with self.lock:
            if self.cached_token and not self.cached_token.is_expired:
                return self.cached_token

            if not self.installation_id:
                self.installation_id = await self._fetch_installation_id()

            self.cached_token = await self._fetch_installation_token()
            logger.info("New GitHub App token acquired.")
            return self.cached_token

    async def get_headers(self) -> GitHubHeaders:
        token_response = await self.get_token()
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _fetch_installation_id(self) -> int:
        try:
            jwt_token = self._generate_jwt()
            url = f"{self.github_host}/orgs/{self.organization}/installation"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()["id"]
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation ID: {e}"
            ) from e

    async def _fetch_installation_token(self) -> GitHubToken:
        try:
            jwt_token = self._generate_jwt()
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

    def _generate_jwt(self) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self.app_id,
            "iat": now,
            "exp": now + timedelta(minutes=self.JWT_EXPIRY_MINUTES),
        }
        decoded_private_key = base64.b64decode(self.private_key)
        return jwt.encode(payload, decoded_private_key, algorithm="RS256")
