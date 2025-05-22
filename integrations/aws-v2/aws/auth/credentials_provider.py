from abc import ABC, abstractmethod
from typing import Optional, Any

from aiobotocore.session import AioSession


from aiobotocore.credentials import (
    AioRefreshableCredentials,
    AioCredentials,
    create_assume_role_refresher,
)

AioCredentialsType = AioCredentials | AioRefreshableCredentials


class CredentialsProviderError(Exception): ...


class CredentialProvider(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._session = AioSession(
            aws_access_key_id=config.get("aws_access_key_id"),
            aws_secret_access_key=config.get("aws_secret_access_key"),
        )

    @abstractmethod
    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...


class StaticCredentialProvider(CredentialProvider):
    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioCredentials:
        return AioCredentials(
            self.aws_access_key_id, self.aws_secret_access_key, token=None
        )

    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession:
        creds = self.get_credentials(region, **kwargs)
        session = AioSession()
        session._credentials = creds
        return session


class AssumeRoleProvider(CredentialProvider):
    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioRefreshableCredentials:
        try:
            async with self._session.create_client("sts", region_name=region) as sts:
                role_arn = kwargs["role_arn"]
                refresher = create_assume_role_refresher(
                    sts,
                    {
                        "RoleArn": role_arn,
                        "RoleSessionName": kwargs.get(
                            "role_session_name", "RoleSessionName"
                        ),
                    },
                )
                metadata = await refresher()
                return AioRefreshableCredentials.create_from_metadata(
                    metadata=metadata, refresh_using=refresher, method="sts-assume-role"
                )
        except Exception as e:
            raise CredentialsProviderError(f"Failed to assume role: {e}")

    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession:
        creds = await self.get_credentials(region, **kwargs)
        session = AioSession()
        session._credentials = creds
        return session
