import os
from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioRefreshableCredentials
from aws.auth.utils import CredentialsProviderError
from loguru import logger
from typing import Any, Awaitable, Callable, Dict


class AssumeRoleWithWebIdentityProvider(CredentialProvider):
    """
    A credential provider that provides temporary credentials for assuming a role with web identity.
    This provider reads the web identity token from a file specified by AWS_WEB_IDENTITY_TOKEN_FILE
    environment variable and uses STS assume_role_with_web_identity API to get credentials.

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

    def _read_web_identity_token(self) -> str:
        """Read the web identity token from the file specified by AWS_WEB_IDENTITY_TOKEN_FILE."""
        token_file = os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
        if not token_file:
            raise CredentialsProviderError(
                "AWS_WEB_IDENTITY_TOKEN_FILE environment variable is required for AssumeRoleWithWebIdentityProvider"
            )

        try:
            with open(token_file, "r") as file:
                token = file.read().strip()
                if not token:
                    raise CredentialsProviderError(
                        f"Web identity token file {token_file} is empty"
                    )
                return token
        except FileNotFoundError:
            raise CredentialsProviderError(
                f"Web identity token file {token_file} not found"
            )
        except Exception as e:
            raise CredentialsProviderError(
                f"Failed to read web identity token from {token_file}: {e}"
            )

    async def _create_web_identity_refresher(
        self, **kwargs: Any
    ) -> Callable[[], Awaitable[Dict[str, Any]]]:
        """Create a refresher function for web identity credentials."""
        role_arn = kwargs["role_arn"]
        role_session_name = kwargs.get("role_session_name", "OceanWebIdentitySession")
        duration_seconds = kwargs.get("duration_seconds", 3600)

        async def refresher() -> Dict[str, Any]:
            """Refresh credentials by calling assume_role_with_web_identity."""
            try:
                web_identity_token = self._read_web_identity_token()
                # This is required for the STS client to work
                # Since the STS client checks for the AWS_ROLE_ARN environment variable and if it's not set, it will fail
                os.environ["AWS_ROLE_ARN"] = role_arn

                async with self.aws_client_factory_session.create_client(
                    "sts", region_name=kwargs.get("region")
                ) as sts_client:
                    assume_role_params = {
                        "RoleArn": role_arn,
                        "RoleSessionName": role_session_name,
                        "WebIdentityToken": web_identity_token,
                        "DurationSeconds": duration_seconds,
                    }

                    # Add optional provider_id if specified
                    if "provider_id" in kwargs:
                        assume_role_params["ProviderId"] = kwargs["provider_id"]

                    response = await sts_client.assume_role_with_web_identity(
                        **assume_role_params
                    )
                    credentials = response["Credentials"]

                    # Return metadata in the format expected by AioRefreshableCredentials
                    return {
                        "access_key": credentials["AccessKeyId"],
                        "secret_key": credentials["SecretAccessKey"],
                        "token": credentials["SessionToken"],
                        "expiry_time": credentials["Expiration"].isoformat(),
                    }
            except Exception as e:
                logger.error(f"Failed to refresh web identity credentials: {e}")
                raise CredentialsProviderError(
                    f"Failed to refresh web identity credentials: {e}"
                ) from e

        return refresher

    async def get_credentials(self, **kwargs: Any) -> AioRefreshableCredentials:
        try:
            role_arn = kwargs["role_arn"]
            if not role_arn:
                raise CredentialsProviderError(
                    "role_arn is required for AssumeRoleWithWebIdentityProvider"
                )

            refresher = await self._create_web_identity_refresher(**kwargs)

            # Get initial credentials
            metadata = await refresher()

            # Create refreshable credentials
            web_identity_credentials = AioRefreshableCredentials.create_from_metadata(
                metadata=metadata,
                refresh_using=refresher,
                method="sts-assume-role-with-web-identity",
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
        web_identity_session = AioSession()
        setattr(web_identity_session, "_credentials", web_identity_credentials)
        return web_identity_session
