from aws.auth.providers.base import CredentialProvider, AioCredentialsType
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials
from typing import Any


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
        if access_key and secret_key:
            return AioCredentials(access_key, secret_key, token=token)
        # If no explicit credentials provided, return None to use boto3 credential chain
        return None

    async def get_session(self, **kwargs: Any) -> AioSession:
        session = AioSession()
        credentials = await self.get_credentials(**kwargs)
        if credentials:
            setattr(session, "_credentials", credentials)
        # If credentials is None, session will use boto3 credential chain
        return session
