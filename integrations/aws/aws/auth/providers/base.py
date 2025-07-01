from abc import ABC, abstractmethod
from typing import Any, Union
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials, AioRefreshableCredentials

AioCredentialsType = Union[AioCredentials, AioRefreshableCredentials]

class CredentialProvider(ABC):
    """
    Base class for credential providers.
    """
    @abstractmethod
    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, **kwargs: Any) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ... 