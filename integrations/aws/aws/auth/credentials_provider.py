from abc import ABC, abstractmethod
from typing import Any, Union, cast
from aiobotocore.session import AioSession
from aiobotocore.credentials import (
    AioRefreshableCredentials,
    AioCredentials,
    create_assume_role_refresher,
)
from aws.auth.utils import CredentialsProviderError

AioCredentialsType = Union[AioCredentials, AioRefreshableCredentials]


class CredentialProvider(ABC):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._session = AioSession()

    @abstractmethod
    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType: ...

    @abstractmethod
    async def get_session(self, **kwargs: Any) -> AioSession: ...

    @property
    @abstractmethod
    def is_refreshable(self) -> bool: ...


class StaticCredentialProvider(CredentialProvider):
    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, **kwargs: Any) -> AioCredentials:
        session = AioSession()
        creds = await session.get_credentials()
        if creds is not None:
            return creds
        # Fallback: try to use credentials from config
        access_key = self.config.get("aws_access_key_id")
        secret_key = self.config.get("aws_secret_access_key")
        if isinstance(access_key, str) and isinstance(secret_key, str):
            return AioCredentials(access_key, secret_key, token=None)
        raise CredentialsProviderError(
            "Missing AWS credentials (no valid credentials in environment or config)"
        )

    async def get_session(self, **kwargs: Any) -> AioSession:
        creds = await self.get_credentials(**kwargs)
        session = AioSession()
        cast(Any, session)._credentials = creds
        return session


class AssumeRoleProvider(CredentialProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        # No credential injection here; fallback handled in get_credentials

    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(self, **kwargs: Any) -> AioRefreshableCredentials:
        region = kwargs.get("region")
        role_arn = kwargs.get("role_arn")
        role_session_name = kwargs.get("role_session_name", "RoleSessionName")
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleProvider"
            )
        # Try default session first
        session = self._session
        creds = await session.get_credentials()
        if creds is None:
            # Fallback: try to use credentials from config
            access_key = self.config.get("aws_access_key_id")
            secret_key = self.config.get("aws_secret_access_key")
            if isinstance(access_key, str) and isinstance(secret_key, str):
                cast(Any, session)._credentials = AioCredentials(
                    access_key, secret_key, token=None
                )
            else:
                raise CredentialsProviderError(
                    "Missing AWS credentials (no valid credentials in environment or config)"
                )
        async with session.create_client("sts", region_name=region) as sts:
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

    async def get_session(self, **kwargs: Any) -> AioSession:
        role_arn = kwargs.get("role_arn")
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleProvider"
            )
        credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        cast(Any, session)._credentials = credentials
        return session
