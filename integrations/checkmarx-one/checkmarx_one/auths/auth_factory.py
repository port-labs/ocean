from typing import Optional

from loguru import logger

from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError
from checkmarx_one.auths.oauth import OAuthAuthenticator
from checkmarx_one.auths.token_auth import TokenAuthenticator


class CheckmarxAuthenticatorFactory:
    """
    Factory class for creating Checkmarx One authenticators.
    Automatically selects the appropriate authentication method based on provided credentials.
    """

    @staticmethod
    def create_authenticator(
        iam_url: str,
        tenant: str,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> BaseCheckmarxAuthenticator:
        """
        Create an appropriate authenticator based on provided credentials.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication
            client_id: OAuth client ID (alternative to API key)
            client_secret: OAuth client secret (required with client_id)

        Returns:
            An appropriate authenticator instance

        Raises:
            CheckmarxAuthenticationError: If no valid authentication method is provided
        """

        if api_key:
            logger.debug(f"Creating API key authenticator for tenant {tenant}")
            return TokenAuthenticator(iam_url, tenant, api_key)

        if client_id and client_secret:
            logger.debug(f"Creating OAuth authenticator for tenant {tenant}")
            return OAuthAuthenticator(iam_url, tenant, client_id, client_secret)

        raise CheckmarxAuthenticationError("No valid authentication method provided")
