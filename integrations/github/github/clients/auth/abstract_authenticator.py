from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
from pydantic import BaseModel, PrivateAttr, Field
from dateutil.parser import parse

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
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
    @abstractmethod
    async def get_token(self) -> GitHubToken:
        pass

    @abstractmethod
    async def get_headers(self) -> GitHubHeaders:
        pass

    @property
    def client(self) -> httpx.AsyncClient:
        retry_config = RetryConfig(
            retry_after_headers=[
                "Retry-After",
                "X-RateLimit-Reset",
            ],
            additional_retry_status_codes=[403],
        )

        return OceanAsyncClient(
            retry_config=retry_config,
            timeout=ocean.config.client_timeout,
        )
