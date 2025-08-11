import time
from abc import ABC, abstractmethod
from typing import Any, Optional
import asyncio

from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError

from checkmarx_one.exceptions import CheckmarxAuthenticationError


class BaseCheckmarxAuthenticator(ABC):
    """
    Base class for Checkmarx One authentication.
    Handles common token management and HTTP client setup.
    """

    def __init__(
        self,
        iam_url: str,
        tenant: str,
    ):
        """
        Initialize the base authenticator.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
        """
        self.iam_url = iam_url.rstrip("/")
        self.tenant = tenant
        self.http_client = http_async_client

        # Token management
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._refresh_lock = asyncio.Lock()
        # Optional attributes populated by concrete authenticators
        self.api_key: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None



    @property
    def auth_url(self) -> str:
        """Get the authentication URL for the tenant."""
        return f"{self.iam_url}/auth/realms/{self.tenant}/protocol/openid-connect/token"

    @property
    def is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self._token_expires_at:
            return True
        # Add 60 second buffer for token refresh
        return time.time() >= (self._token_expires_at - 60)

    def _get_cache_key(self) -> str:
        """Generate a unique cache key for this authenticator's token."""
        return (
            f"checkmarx_token_{self.tenant}_{self.iam_url}".replace("/", "_")
            .replace(":", "_")
            .replace(".", "_")
        )

    async def _get_cached_token(self) -> Optional[dict[str, Any]]:
        """Get the cached token if it exists and is not expired."""
        try:
            cache_key = self._get_cache_key()
            cached_data = await ocean.app.cache_provider.get(cache_key)

            if cached_data and isinstance(cached_data, dict):
                cached_time = cached_data.get("cached_at", 0)
                cached_expires_at = (
                    cached_data.get("expires_in", 1800) / 60
                )  # Convert to minutes
                current_time = time.time()
                if current_time - cached_time < cached_expires_at - 1:
                    logger.info(f"Using cached token for tenant {self.tenant}")
                    return cached_data
                else:
                    logger.info(f"Cached token expired for tenant {self.tenant}")

            return None
        except FailedToReadCacheError as e:
            logger.warning(f"Failed to read cached token: {str(e)}")
            return None

    async def _cache_token(self, token_data: dict[str, Any]) -> None:
        """Cache the token data with current timestamp."""
        try:
            cache_key = self._get_cache_key()
            cache_data = {**token_data, "cached_at": time.time()}
            await ocean.app.cache_provider.set(cache_key, cache_data)
            logger.debug(f"Token cached successfully for tenant {self.tenant}")
        except FailedToWriteCacheError as e:
            logger.warning(f"Failed to cache token: {str(e)}")

    @abstractmethod
    async def _authenticate(self) -> dict[str, Any]:
        """Authenticate and return token response. Must be implemented by subclasses."""
        pass

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the appropriate method."""
        try:
            async with self._refresh_lock:
                if self._access_token and not self.is_token_expired:
                    logger.debug(
                        "Another coroutine refreshed the token while waiting for lock"
                    )
                    return

                token_response = await self._authenticate()

            self._access_token = token_response["access_token"]
            self._refresh_token = token_response["refresh_token"]

            # Token expires in seconds, store absolute time
            expires_in = token_response.get(
                "expires_in", 1800
            )  # Default 30 minutes
            self._token_expires_at = time.time() + expires_in

            # Cache the token data
            await self._cache_token(token_response)

            logger.info(
                f"Successfully refreshed access token, expires in {expires_in} seconds"
            )

        except Exception as e:
            logger.error(f"Failed to refresh access token: {str(e)}")
            raise CheckmarxAuthenticationError(f"Token refresh failed: {str(e)}")

    async def _get_access_token(self) -> str | None:
        """Get a valid access token, checking cache first then refreshing if necessary."""
        # First, try to get from cache
        cached_token = await self._get_cached_token()
        if cached_token:
            self._access_token = cached_token["access_token"]
            self._refresh_token = cached_token["refresh_token"]
            expires_in = cached_token.get("expires_in", 1800)
            self._token_expires_at = time.time() + expires_in
            return self._access_token

        # If not in cache or expired, refresh the token
        if not self._access_token or self.is_token_expired:
            await self._refresh_access_token()

        return self._access_token

    async def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        access_token = await self._get_access_token()
        if access_token is None:
            raise CheckmarxAuthenticationError("Failed to obtain access token")
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def refresh_token(self) -> None:
        """Force refresh the access token."""
        await self._refresh_access_token()
