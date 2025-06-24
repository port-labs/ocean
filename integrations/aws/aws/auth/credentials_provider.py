from abc import ABC, abstractmethod
from typing import Optional, Any, Union, cast
from aiobotocore.session import AioSession
from aiobotocore.credentials import (
    AioRefreshableCredentials,
    AioCredentials,
    create_assume_role_refresher,
)

AioCredentialsType = Union[AioCredentials, AioRefreshableCredentials]


class CredentialsProviderError(Exception): ...


class CredentialProvider(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._session = AioSession()

    @abstractmethod
    async def get_credentials(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...


class StaticCredentialProvider(CredentialProvider):
    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioCredentials:
        access_key = self.config.get("aws_access_key_id")
        secret_key = self.config.get("aws_secret_access_key")
        if not isinstance(access_key, str) or not isinstance(secret_key, str):
            raise CredentialsProviderError("Missing AWS credentials")
        return AioCredentials(access_key, secret_key, token=None)

    async def get_session(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioSession:
        creds = await self.get_credentials(region)
        session = AioSession()
        cast(Any, session)._credentials = creds
        return session


class AssumeRoleProvider(CredentialProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        access_key = self.config.get("aws_access_key_id")
        secret_key = self.config.get("aws_secret_access_key")

        if access_key is not None and secret_key is not None:
            cast(Any, self._session)._credentials = AioCredentials(
                access_key, secret_key, token=None
            )

    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioRefreshableCredentials:
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleProvider"
            )
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

    async def get_session(
        self,
        region: Optional[str],
        role_arn: Optional[str] = None,
        role_session_name: str = "RoleSessionName",
    ) -> AioSession:
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleProvider"
            )
        credentials = await self.get_credentials(region, role_arn, role_session_name)
        session = AioSession()
        cast(Any, session)._credentials = credentials
        return session
