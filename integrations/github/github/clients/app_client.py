from typing import Any, Dict, Optional, Self, override
import httpx
import jwt
import time

from port_ocean.utils import http_async_client

from github.clients.rest_client import GithubRestClient


class GithubAppRestClient(GithubRestClient):
    def __init__(
        self, organization: str, github_host: str, app_id: str, private_key: str
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.github_host = github_host
        self.organization = organization

    async def set_up(self) -> Self:
        token = await self._get_installation_token()
        super().__init__(token, self.organization, self.github_host)
        return self

    async def _get_installation_token(self) -> str:
        install_id = await self._get_installation_id()
        jwt_token = self._generate_jwt_token()

        url = f"{self.github_host.rstrip('/')}/app/installations/{install_id}/access_tokens"
        headers = {
            "accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
        }
        r = await http_async_client.post(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["token"]

    async def _get_installation_id(self) -> int:
        jwt_token = self._generate_jwt_token()

        url = f"{self.github_host.rstrip('/')}/orgs/{self.organization}/installation"
        headers = {
            "accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
        }
        r = await http_async_client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["id"]

    def _generate_jwt_token(self) -> str:
        payload = {
            "iss": self.app_id,
            "iat": int(time.monotonic()),
            "exp": int(time.monotonic() + (10 * 60)),
        }

        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    @override
    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        try:
            return await super().send_api_request(endpoint, method, params, json_data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                t = await self._get_installation_token()
                super().token = t
                return await self.send_api_request(endpoint, method, params, json_data)
            else:
                raise
