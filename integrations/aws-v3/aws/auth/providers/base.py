from abc import ABC, abstractmethod
from typing import Any, Union
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioRefreshableCredentials, AioCredentials

AioCredentialsType = Union[AioCredentials, AioRefreshableCredentials, None]


class CredentialProvider(ABC):
    """
    Base class for credential providers.
    """

    def __init__(self, config: dict[str, Any] = {}):
        self.config = config or {}
        # Long-lived session used as a factory for creating AWS service clients
        self.aws_client_factory_session = AioSession()

    @abstractmethod
    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, **kwargs: Any) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...
