from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from aiobotocore.credentials import (
    AioRefreshableCredentials,
    create_assume_role_refresher,
)
from aws.auth.utils import CredentialsProviderError
from loguru import logger
from typing import Any
import os


class AssumeRoleWithWebIdentityProvider(CredentialProvider):
    """
    A credential provider that assumes an IAM role using a Web Identity Token (OIDC).
    This is used inside EKS pods where a service account is mapped to an IAM role via IRSA.

    Tokens are typically short-lived (~1hr) and auto-refreshed.
    """

    @property
    def is_refreshable(self) -> bool:
        return True

    async def get_credentials(self, **kwargs: Any) -> AioRefreshableCredentials:
        try:
            async with self.aws_client_factory_session.create_client(
                "sts", region_name=kwargs.get("region")
            ) as sts_client:

                token_file = kwargs.get("web_identity_token_file") or os.environ.get(
                    "AWS_WEB_IDENTITY_TOKEN_FILE"
                )
                session_name = kwargs.get("role_session_name", "OceanOIDCSession")

                if not token_file or not os.path.exists(token_file):
                    raise CredentialsProviderError(
                        f"Web identity token file not found: {token_file}"
                    )

                assume_role_params = {
                    "RoleArn": kwargs["role_arn"],
                    "RoleSessionName": session_name,
                    "WebIdentityTokenFile": token_file,
                }

                refresher = create_assume_role_refresher(
                    client=sts_client,
                    params=assume_role_params,
                )

                metadata = await refresher()
                web_identity_credentials = (
                    AioRefreshableCredentials.create_from_metadata(
                        metadata=metadata,
                        refresh_using=refresher,
                        method="sts-assume-role-web-identity",
                    )
                )

                return web_identity_credentials
        except Exception as e:
            logger.error(f"Failed to assume role with web identity: {e}")
            raise CredentialsProviderError(
                f"Failed to assume role with web identity: {e}"
            ) from e

    async def get_session(self, **kwargs: Any) -> AioSession:
        role_arn = kwargs.get("role_arn")
        if not role_arn:
            raise CredentialsProviderError(
                "role_arn is required for AssumeRoleWithWebIdentityProvider"
            )

        web_identity_credentials = await self.get_credentials(**kwargs)
        session = AioSession()
        setattr(session, "_credentials", web_identity_credentials)
        return session
