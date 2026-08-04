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
    def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        """Yield (AccountInfo, AioSession) pairs for each account managed by this strategy."""
        pass

    @abstractmethod
    async def get_session_for_account(self, account_id: str) -> AioSession | None:
        """Return a pre-validated session for the given account ID, if available."""
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
