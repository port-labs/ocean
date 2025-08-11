from typing import Any, Optional


from checkmarx_one.auths.auth_factory import CheckmarxAuthenticatorFactory
from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator


class CheckmarxClientAuthenticator(BaseCheckmarxAuthenticator):
    """
    Handles authentication for Checkmarx One API.
    Supports both OAuth client and API key authentication methods.

    This class maintains backward compatibility with the original interface.
    For new code, consider using the factory pattern directly.

    This class is implemented as a singleton to ensure only one instance
    per unique set of authentication parameters exists.
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
        authenticator = CheckmarxAuthenticatorFactory.create_authenticator(
            iam_url=iam_url,
            tenant=tenant,
            api_key=api_key,
            client_id=client_id,
            client_secret=client_secret,
        )

        self.__dict__.update(authenticator.__dict__)
        self._authenticator = authenticator

    async def _authenticate(self) -> dict[str, Any]:
        """Delegate to the underlying authenticator."""
        return await self._authenticator._authenticate()

    async def get_auth_headers(self) -> dict[str, str]:
        """Delegate to the underlying authenticator."""
        return await self._authenticator.get_auth_headers()
