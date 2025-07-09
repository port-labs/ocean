from aws.auth.providers.base import CredentialProvider, AioCredentialsType
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials
from typing import Any
from aws.auth._helpers.exceptions import CredentialsProviderError


class StaticCredentialProvider(CredentialProvider):
    """
    Note: Static credentials (IAM User) should not be used for multi-account setups
    """

    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType:
        try:
            access_key = kwargs["aws_access_key_id"]
            secret_key = kwargs["aws_secret_access_key"]
            token = kwargs.get("aws_session_token")
            return AioCredentials(access_key, secret_key, token=token)
        except Exception as e:
            raise CredentialsProviderError(f"Failed to get credentials: {e}")

    async def get_session(self, **kwargs: Any) -> AioSession:
        """For static credentials, overwrite the integration's identity with the credentials or identity provided.
        While we can equally create a new session, this is more efficient as we don't need another session instance.
        """
        session = AioSession()  # self._integration_session
        credentials = await self.get_credentials(**kwargs)
        setattr(session, "_credentials", credentials)
        return session
