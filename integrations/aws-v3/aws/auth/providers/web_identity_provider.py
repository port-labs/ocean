from aws.auth.providers.base import CredentialProvider, AioCredentialsType
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials
from aiobotocore.config import AioConfig
from aws.auth.utils import CredentialsProviderError
from loguru import logger
from typing import Any


class WebIdentityCredentialProvider(CredentialProvider):
    """
    Credential provider that uses web identity tokens to assume a role with AWS STS (assume_role_with_web_identity).
    """

    @property
    def is_refreshable(self) -> bool:
        return False

    async def get_credentials(self, **kwargs: Any) -> AioCredentialsType:
        try:
            async with self.aws_client_factory_session.create_client(
                "sts",
                region_name=kwargs.get("region"),
                config=AioConfig(signature_version="UNSIGNED"),
            ) as sts_client:
                assume_role_params = {
                    "RoleArn": kwargs["role_arn"],
                    "RoleSessionName": kwargs.get(
                        "role_session_name", "OceanWebIdentitySession"
                    ),
                    "WebIdentityToken": kwargs["oidc_token"],
                }

                response = await sts_client.assume_role_with_web_identity(
                    **assume_role_params
                )
                creds = response["Credentials"]

                return AioCredentials(
                    creds["AccessKeyId"],
                    creds["SecretAccessKey"],
                    token=creds["SessionToken"],
                )
        except Exception as e:
            logger.error(f"Failed to get web identity credentials: {e}")
            raise CredentialsProviderError(
                f"Failed to get web identity credentials: {e}"
            ) from e

    async def get_session(self, **kwargs: Any) -> AioSession:
        credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        setattr(session, "_credentials", credentials)
        return session
