from typing import Optional, Any

from aiobotocore.session import AioSession
from auth.credential_providers._abstract import CredentialProvider


from aiobotocore.credentials import (
    AioCredentials,
)
from auth.credential_providers._abstract import AioCredentialsType


class StaticCredentialProvider(CredentialProvider):
    """
    A credential provider that provides static credentials.
    The credentials are not refreshed.
    """

    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(
        self, region: Optional[str], **kwargs: Any
    ) -> AioCredentialsType:
        return AioCredentials(
            self.config["aws_access_key_id"],
            self.config["aws_secret_access_key"],
            token=None,
        )

    async def get_session(self, region: Optional[str], **kwargs: Any) -> AioSession:
        creds = self.get_credentials(region, **kwargs)
        session = AioSession()
        session._credentials = creds
        return session
