from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
from pydantic import BaseModel, PrivateAttr, Field
from dateutil.parser import parse

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.utils.cache import cache_coroutine_result
from loguru import logger

import httpx


class GitHubToken(BaseModel):
    token: str
    expires_at: Optional[str] = None
    _time_buffer: timedelta = PrivateAttr(default_factory=lambda: timedelta(minutes=5))

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False

        expires_at_dt = parse(self.expires_at)
        return datetime.now(timezone.utc) >= (expires_at_dt - self._time_buffer)


class GitHubHeaders(BaseModel):
    authorization: str = Field(alias="Authorization")
    accept: str = Field(alias="Accept", default="application/vnd.github+json")
    x_github_api_version: str = Field(
        alias="X_GitHub_Api_Version", default="2022-11-28"
    )

    def as_dict(self) -> Dict[str, str]:
        headers = self.dict(by_alias=True)
        headers["X-GitHub-Api-Version"] = headers.pop("X_GitHub_Api_Version")
        return headers


class AbstractGitHubAuthenticator(ABC):
    _http_client: Optional[httpx.AsyncClient] = None

    @abstractmethod
    async def get_token(self, **kwargs: Any) -> GitHubToken:
        pass

    @abstractmethod
    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        pass

    @property
    def client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            retry_config = RetryConfig(
                retry_after_headers=[
                    "Retry-After",
                    "X-RateLimit-Reset",
                ]
            )
            self._http_client = OceanAsyncClient(
                retry_config=retry_config,
                timeout=ocean.config.client_timeout,
            )
        return self._http_client

    @cache_coroutine_result()
    async def is_personal_org(self, github_host: str, organization: str) -> bool:
        try:
            url = f"{github_host}/users/{organization}"
            response = await self.client.get(url)
            response.raise_for_status()
            user_data = response.json()
            return user_data["type"] == "User"
        except Exception:
            logger.exception(
                "Failed to check if organization is personal, assuming it is not a personal org"
            )
            return False
