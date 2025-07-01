from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Any


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    async def healthcheck(self) -> bool:
        pass

    @abstractmethod
    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        yield  # type: ignore [misc]

    @abstractmethod
    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        pass
