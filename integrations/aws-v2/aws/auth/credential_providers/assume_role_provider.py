from typing import Optional, Any

from aiobotocore.session import AioSession
from auth.credential_providers._abstract import CredentialProvider


from aiobotocore.credentials import (
    AioRefreshableCredentials,
    create_assume_role_refresher,
)
from aws.helpers.exceptions import CredentialsProviderError


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

    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioRefreshableCredentials:
        try:
            async with self._session.create_client("sts", region_name=region) as sts:
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

    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession:
        creds = await self.get_credentials(region, **kwargs)
        session = AioSession()
        session._credentials = creds
        return session
