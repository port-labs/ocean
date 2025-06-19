from abc import ABC, abstractmethod
from typing import Optional, Any, final

from aiobotocore.session import AioSession
from aiobotocore.credentials import AioRefreshableCredentials, AioCredentials

AioCredentialsType = AioCredentials | AioRefreshableCredentials


class CredentialProvider(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...
