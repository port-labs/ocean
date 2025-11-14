import asyncio
import base64
from typing import Any, Optional
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

    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        token_response = await self.get_token(**kwargs)
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    async def _fetch_installation_id(self, jwt_token: str) -> int:
        try:
            url = f"{self.github_host}/orgs/{self.organization}/installation"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()["id"]
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
