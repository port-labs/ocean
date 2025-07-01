from aws.auth.providers.base import CredentialProvider
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

    async def get_credentials(self, **kwargs: Any) -> AioCredentials:
        return AioCredentials(
            kwargs["aws_access_key_id"],
            kwargs["aws_secret_access_key"],
            token=None,
        )

    async def get_session(self, **kwargs: Any) -> AioSession:
        credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        setattr(session, "_credentials", credentials)
        return session
