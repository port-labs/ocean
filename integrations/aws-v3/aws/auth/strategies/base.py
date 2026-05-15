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
    async def session_for_account(self, account_id: str) -> AioSession | None:
        """Return a validated `AioSession` for the given account ID, or `None`.

        Live-event handlers use this to resolve the right `AioSession` from the
        `account` field carried in the EventBridge envelope, without invoking
        the strategy's account-discovery iterator. Strategies that have not
        completed a healthcheck must do so on first call.
        """
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
