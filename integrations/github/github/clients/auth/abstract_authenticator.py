from typing import Dict, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel, PrivateAttr, Field
from datetime import datetime, timezone
from port_ocean.utils import http_async_client
import httpx


class GitHubToken(BaseModel):
    token: str
    expires_at: Optional[datetime] = None
    _retrieved_at: datetime = PrivateAttr(default_factory=datetime.now)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at


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
        return http_async_client
