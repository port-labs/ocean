from typing import Dict
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
import httpx


class HarborToken(BaseModel):
    token: str


class HarborHeaders(BaseModel):
    authorization: str = Field(alias="Authorization")
    accept: str = Field(alias="Accept", default="application/json")

    class Config:
        allow_population_by_field_name = True

    def as_dict(self) -> Dict[str, str]:
        return self.dict(by_alias=True)


class AbstractHarborAuthenticator(ABC):
    """Abstract base class for Harbor authentication methods"""

    @abstractmethod
    async def get_token(self) -> HarborToken:
        """Get Harbor authentication token"""
        pass

    @abstractmethod
    async def get_headers(self) -> HarborHeaders:
        """Get headers required for Harbor API requests"""
        pass

    @property
    def client(self) -> httpx.AsyncClient:
        """Get configured HTTP client with Harbor-specific retry settings"""
        retry_config = RetryConfig(
            retry_after_headers=[
                "Retry-After",
                "X-RateLimit-Reset",
            ]
        )

        return OceanAsyncClient(
            retry_config=retry_config,
            timeout=ocean.config.client_timeout,
        )
