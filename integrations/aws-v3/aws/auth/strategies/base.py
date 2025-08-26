from aws.auth.providers.base import CredentialProvider
from aws.auth.types import AccountInfo
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[AccountInfo, AioSession]]:
        """Yield (AccountInfo, AioSession) pairs for each account managed by this strategy."""
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
