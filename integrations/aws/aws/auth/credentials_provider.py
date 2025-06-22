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
        self._session = AioSession()

    @abstractmethod
    async def get_credentials(self, region: Optional[str]) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, region: Optional[str]) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...


class StaticCredentialProvider(CredentialProvider):
    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, region: Optional[str]) -> AioCredentials:
        return AioCredentials(
            self.config.get("aws_access_key_id"),
            self.config.get("aws_secret_access_key"),
            token=None,
        )

    async def get_session(self, region: Optional[str]) -> AioSession:
        creds = await self.get_credentials(region)
        session = AioSession()
        session._credentials = creds
        return session


class AssumeRoleProvider(CredentialProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        if config.get("aws_access_key_id") and config.get("aws_secret_access_key"):
            self._session._credentials = AioCredentials(
                config.get("aws_access_key_id"),
                config.get("aws_secret_access_key"),
                token=None,
            )

    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(
        self,
        region: Optional[str],
        role_arn: str,
        role_session_name: str = "RoleSessionName",
    ) -> AioRefreshableCredentials:
        try:
            async with self._session.create_client("sts", region_name=region) as sts:
                refresher = create_assume_role_refresher(
                    sts,
                    {
                        "RoleArn": role_arn,
                        "RoleSessionName": role_session_name,
                    },
                )
                metadata = await refresher()
                credentials = AioRefreshableCredentials.create_from_metadata(
                    metadata=metadata, refresh_using=refresher, method="sts-assume-role"
                )
                return credentials
        except Exception as e:
            raise CredentialsProviderError(f"Failed to assume role: {e}")

    async def get_session(
        self,
        region: Optional[str],
        role_arn: str,
        role_session_name: str = "RoleSessionName",
    ) -> AioSession:
        credentials = await self.get_credentials(region, role_arn, role_session_name)
        session = AioSession()
        session._credentials = credentials
        return session
