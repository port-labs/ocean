from typing import Optional


from auth_factory import CheckmarxAuthenticatorFactory
from base_auth import BaseCheckmarxAuthenticator


class CheckmarxAuthenticator(BaseCheckmarxAuthenticator):
    """
    Handles authentication for Checkmarx One API.
    Supports both OAuth client and API key authentication methods.

    This class maintains backward compatibility with the original interface.
    For new code, consider using the factory pattern directly.
    """

    def __init__(
        self,
        iam_url: str,
        tenant: str,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize the Checkmarx One authenticator.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication
            client_id: OAuth client ID (alternative to API key)
            client_secret: OAuth client secret (required with client_id)
        """
        # Create the appropriate authenticator using the factory
        authenticator = CheckmarxAuthenticatorFactory.create_authenticator(
            iam_url=iam_url,
            tenant=tenant,
            api_key=api_key,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Copy all attributes from the created authenticator
        self.__dict__.update(authenticator.__dict__)

        # Store the underlying authenticator for method delegation
        self._authenticator = authenticator

    async def _authenticate(self):
        """Delegate to the underlying authenticator."""
        return await self._authenticator._authenticate()

    async def get_auth_headers(self):
        """Delegate to the underlying authenticator."""
        return await self._authenticator.get_auth_headers()

    async def refresh_token(self):
        """Delegate to the underlying authenticator."""
        return await self._authenticator.refresh_token()
