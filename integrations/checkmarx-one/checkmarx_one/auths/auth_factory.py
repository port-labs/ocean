from typing import Optional

from loguru import logger

from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError
from checkmarx_one.auths.token_auth import TokenAuthenticator


class CheckmarxAuthenticatorFactory:
    """
    Factory class for creating Checkmarx One authenticators.
    Only token authentication is supported for now.
    """

    @staticmethod
    def create_authenticator(
        iam_url: str,
        tenant: str,
        api_key: Optional[str] = None,
    ) -> BaseCheckmarxAuthenticator:
        """
        Create a token authenticator based on provided credentials.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication

        Returns:
            A token authenticator instance

        Raises:
            CheckmarxAuthenticationError: If no valid API key is provided
        """

        if api_key:
            logger.debug(f"Creating API key authenticator for tenant {tenant}")
            return TokenAuthenticator(iam_url, tenant, api_key)

        raise CheckmarxAuthenticationError("No valid API key provided. Only token authentication is supported for now.")
