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
    """
    A credential provider that provides static credentials.
    The credentials are not refreshed.
    """

    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, **kwargs: Any) -> AioCredentials:
        return AioCredentials(
            self.config["aws_access_key_id"],
            self.config["aws_secret_access_key"],
            token=None,
        )

    async def get_session(self, **kwargs: Any) -> AioSession:
        creds = self.get_credentials(kwargs.get("region"), **kwargs)
        session = AioSession()
        session._credentials = creds
        return session


class AssumeRoleProvider(CredentialProvider):
    """
    A credential provider that provides temporary credentials for assuming a role.
    The refresh process works like this:
        When a session is created, it gets AioRefreshableCredentials
        These credentials are stored in the session
        When an AWS API call is made:
        The session checks if it needs credentials
        If needed, it calls get_frozen_credentials() from the AioRefreshableCredentials
        If the credentials are expired or about to expire, the refresh function is called
        The refreshed credentials are used for the API call
    """

    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(self, **kwargs: Any) -> AioRefreshableCredentials:
        try:
            async with self._session.create_client(
                "sts", region_name=kwargs.get("region")
            ) as sts:
                role_arn = kwargs["role_arn"]
                assume_role_params = {
                    "RoleArn": role_arn,
                    "RoleSessionName": kwargs.get(
                        "role_session_name", "RoleSessionName"
                    ),
                }

                # Add external ID if provided in kwargs
                if "external_id" in kwargs:
                    assume_role_params["ExternalId"] = kwargs["external_id"]

                refresher = create_assume_role_refresher(
                    sts,
                    assume_role_params,
                )
                metadata = await refresher()
                return AioRefreshableCredentials.create_from_metadata(
                    metadata=metadata, refresh_using=refresher, method="sts-assume-role"
                )
        except Exception as e:
            raise CredentialsProviderError(f"Failed to assume role: {e}")

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
