from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any, TypedDict, NotRequired


class AccountDetails(TypedDict):
    """TypedDict representing AWS account details."""

    Id: str
    Name: str
    Arn: NotRequired[str]


class AccountContext(TypedDict):
    """TypedDict representing the context for an AWS account session."""

    details: AccountDetails
    session: AioSession


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    def get_account_sessions(
        self,
    ) -> AsyncIterator[AccountContext]: ...


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass
