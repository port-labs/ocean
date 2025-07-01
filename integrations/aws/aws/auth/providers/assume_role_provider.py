from aws.auth.providers.base import CredentialProvider, AioCredentialsType
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioRefreshableCredentials, create_assume_role_refresher
from aws.auth.utils import CredentialsProviderError
from loguru import logger
from typing import Any

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
            async with AioSession().create_client(
                "sts", region_name=kwargs.get("region")
            ) as sts:
                role_arn = kwargs["role_arn"]
                assume_role_params = {
                    "RoleArn": role_arn,
                    "RoleSessionName": kwargs.get(
                        "role_session_name", "OceanRoleSession"
                    ),
                }
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
            logger.error(f"Failed to assume role: {e}")
            raise CredentialsProviderError(f"Failed to assume role: {e}") from e

    async def get_session(self, **kwargs: Any) -> AioSession:
        role_arn = kwargs.get("role_arn")
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleProvider"
            )
        credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        setattr(session, "_credentials", credentials)
        return session 