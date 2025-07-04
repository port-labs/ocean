from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    async def create_session(self, **kwargs: Any) -> AioSession:
        pass

    @abstractmethod
    def create_session_for_each_account(
        self, **kwargs: Any
    ) -> AsyncIterator[AioSession]:
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
