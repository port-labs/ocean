from aws.auth.providers.base import CredentialProvider, AioCredentialsType
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials
from typing import Any
from aws.auth.utils import CredentialsProviderError


class StaticCredentialProvider(CredentialProvider):
    """
    Note: Static credentials (IAM User) should not be used for multi-account setups
    """

    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType:
        access_key = kwargs.get("aws_access_key_id")
        secret_key = kwargs.get("aws_secret_access_key")
        token = kwargs.get("aws_session_token")

        if not (access_key and secret_key):
            raise CredentialsProviderError(
                "Both aws_access_key_id and aws_secret_access_key are required for static credentials"
            )

        return AioCredentials(access_key, secret_key, token=token)

    async def get_session(self, **kwargs: Any) -> AioSession:
        credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        setattr(session, "_credentials", credentials)
        return session
