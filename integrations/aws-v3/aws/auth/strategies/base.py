from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config
        self._inaccessible_accounts: dict[str, str] = {}

    @property
    def inaccessible_accounts(self) -> dict[str, str]:
        """Account IDs that failed assume-role during health check, mapped to the error."""
        return self._inaccessible_accounts

    @abstractmethod
    def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        """Yield (AccountInfo, AioSession) pairs for each account managed by this strategy."""
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
