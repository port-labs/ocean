from typing import Any, Dict, Optional
from sailpoint.utils.logging import Logger
from sailpoint.connector import SailPointAuthManager
from sailpoint.utils.pagination import PaginatorProtocol, LimitOffsetPagination


class SailpointClient:
    """
    Client for interacting with the SailPoint IdentityNow API

    (https://developer.sailpoint.com/docs/identitynow/).

    Uses:
    - OAuth2 for authentication
    - Async HTTP requests for efficient API calls
    - Handles token refresh and error scenarios

    Supports:
    - Fetching user details
    - Managing identities
    - Accessing and modifying access profiles
    - Handling entitlements and roles
    - Working with governance and compliance

    What it does not do:
    - Directly manage OAuth2 tokens (handled by our SailPointAuthManager)
    - Synchronous API calls (all calls are async)
    - Detailed error handling for specific API endpoints (general error handling is provided)

    Delegates:
    - Authentication to SailPointAuthManager:
    - Logging to our Logger utility
    - Pagination to our Paginator Protocol, such that we can compose with
      different pagination strategies

    """

    def __init__(
        self,
        auth_client: SailPointAuthManager,
        api_headers: Optional[Dict[str, str]] = None,
        api_version: Optional[str] = None,
        paginator: PaginatorProtocol = LimitOffsetPagination(),
    ) -> None:
        self._auth_client = auth_client
        self._base_url = auth_client._base_url
        self._api_headers = api_headers or {}
        self._api_version = auth_client.SAILPOINT_DEFAULT_API_VERSION
        self.logger = Logger
        self.paginator = paginator

        if api_version:
            self._api_version = api_version
