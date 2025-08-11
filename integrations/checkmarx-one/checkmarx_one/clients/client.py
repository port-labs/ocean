from typing import Optional

from checkmarx_one.auths.auth import CheckmarxClientAuthenticator
from checkmarx_one.clients.base_client import CheckmarxOneClient


class CheckmarxClient(CheckmarxOneClient):
    """
    Client for interacting with Checkmarx One API.
    Supports both OAuth client and API key authentication methods.

    This client provides the base HTTP functionality. For resource-specific operations,
    use the appropriate exporters (ProjectExporter, ScanExporter, etc.).
    """

    def __init__(
        self,
        base_url: str,
        iam_url: str,
        tenant: str,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize the Checkmarx One client.

        Args:
            base_url: Base URL for API calls (e.g., https://ast.checkmarx.net)
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication
            client_id: OAuth client ID (alternative to API key)
            client_secret: OAuth client secret (required with client_id)
        """
        # Initialize authenticator
        authenticator = CheckmarxClientAuthenticator(
            iam_url=iam_url,
            tenant=tenant,
            api_key=api_key,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Initialize base client
        super().__init__(base_url, authenticator)
