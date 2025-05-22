from typing import Dict, Optional
import jwt
import time

from port_ocean.utils import http_async_client


# Constant for JWT expiration time delta in seconds. This is 10 minutes
JWT_EXP_DELTA_SECONDS = 10 * 60


class GithubApp:
    def __init__(
        self,
        *,
        organization: str,
        github_host: str,
        app_id: str,
        private_key: str | bytes,
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.github_host = github_host
        self.organization = organization
        self._installation_id: Optional[int] = None

    async def get_token(self) -> str:
        """
        Initializes the client by fetching the installation ID and token.
        """
        if self._installation_id is None:
            self._installation_id = await self._get_installation_id()
        token = await self._get_installation_token(self._installation_id)
        return token

    def _generate_auth_headers(self, jwt_token: str) -> Dict[str, str]:
        """
        Generates standard headers with JWT authorization.
        """
        return {
            "accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
        }

    async def _get_installation_token(self, install_id: int) -> str:
        """
        Fetches an installation access token using a JWT.
        """
        jwt_token = self._generate_jwt_token()

        url = f"{self.github_host.rstrip('/')}/app/installations/{install_id}/access_tokens"
        headers = self._generate_auth_headers(jwt_token)

        r = await http_async_client.post(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["token"]

    async def _get_installation_id(self) -> int:
        """
        Fetches the installation ID for the organization.
        This method is intended to be called only once during initial setup.
        """
        jwt_token = self._generate_jwt_token()

        url = f"{self.github_host.rstrip('/')}/orgs/{self.organization}/installation"
        headers = self._generate_auth_headers(jwt_token)

        r = await http_async_client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["id"]

    def _generate_jwt_token(self) -> str:
        """
        Generates a JWT token for the GitHub App.
        """
        payload = {
            "iss": self.app_id,
            "iat": int(time.monotonic()),
            "exp": int(time.time() + JWT_EXP_DELTA_SECONDS),
        }

        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token
