"""
Slack API client implementation with rate limiting support.
"""
import asyncio
from typing import Any, Dict, Optional, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.exceptions.integration import IntegrationError

class SlackRateLimitError(IntegrationError):
    """Raised when rate limit retries are exhausted."""
    pass

class SlackApiError(IntegrationError):
    """Raised when Slack API returns an error."""
    pass

class SlackApiClient:
    """Client for interacting with Slack's Web API."""

    def __init__(self, token: str):
        """Initialize the Slack API client.

        Args:
            token: Slack API token for authentication
        """
        self.token = token
        self.base_url = "https://slack.com/api"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            },
            timeout=30.0,
            follow_redirects=True
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Make a rate-limited request to the Slack API.

        Args:
            method: HTTP method to use
            endpoint: API endpoint to call
            params: Query parameters
            max_retries: Maximum number of retry attempts for rate limiting
            **kwargs: Additional arguments to pass to httpx

        Returns:
            JSON response from the API

        Raises:
            SlackRateLimitError: If rate limit retries are exhausted
            SlackApiError: If the API request fails
            IntegrationError: For other errors
        """
        url = f"{self.base_url}/{endpoint}"
        attempt = 0
        base_delay = 1

        while True:
            try:
                attempt += 1
                logger.debug(f"Making request to {endpoint} (attempt {attempt}/{max_retries})")

                response = await self.client.request(
                    method,
                    url,
                    params=params,
                    **kwargs
                )

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", base_delay))
                    logger.warning(
                        f"Rate limited on {endpoint}. Waiting {retry_after} seconds. "
                        f"Attempt {attempt}/{max_retries}"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise SlackRateLimitError(
                            f"Max retries ({max_retries}) exceeded for rate limited request"
                        )

                response.raise_for_status()
                data = response.json()

                # Slack API always returns 200 but includes success in response
                if not data.get("ok", False):
                    error = data.get("error", "Unknown error")
                    logger.error(f"Slack API error: {error} for {endpoint}")
                    raise SlackApiError(f"Slack API error: {error}")

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error occurred: {str(e)} for {endpoint}. "
                    f"Status: {e.response.status_code}"
                )
                raise IntegrationError(f"HTTP error occurred: {str(e)}")
            except Exception as e:
                logger.error(f"Error in request to {endpoint}: {str(e)}")
                raise

    async def _paginate(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        cursor_key: str = "cursor",
        items_key: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle pagination for Slack API endpoints.

        Args:
            method: HTTP method to use
            endpoint: API endpoint to call
            params: Base query parameters
            cursor_key: Key for the pagination cursor in response
            items_key: Key for the items in response

        Yields:
            Each page of results
        """
        params = params or {}
        while True:
            response = await self._request(method, endpoint, params=params)

            if items_key:
                yield response.get(items_key, [])
            else:
                yield response

            # Check if there are more pages
            metadata = response.get("response_metadata", {})
            next_cursor = metadata.get("next_cursor")

            if not next_cursor:
                break

            params[cursor_key] = next_cursor

    async def list_channels(
        self,
        exclude_archived: bool = False,
        types: str = "public_channel,private_channel"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all channels in the workspace.

        Args:
            exclude_archived: Whether to exclude archived channels
            types: Comma-separated list of channel types to include

        Yields:
            Each page of channels
        """
        async for channels in self._paginate(
            "GET",
            "conversations.list",
            params={
                "exclude_archived": str(exclude_archived).lower(),
                "types": types,
                "limit": 1000  # Max allowed by Slack
            },
            items_key="channels"
        ):
            yield channels

    async def list_users(self) -> AsyncGenerator[Dict[str, Any], None]:
        """List all users in the workspace.

        Yields:
            Each page of users
        """
        async for users in self._paginate(
            "GET",
            "users.list",
            params={"limit": 1000},  # Max allowed by Slack
            items_key="members"
        ):
            yield users

    async def get_channel_members(
        self,
        channel_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get members of a specific channel.

        Args:
            channel_id: The ID of the channel to get members for

        Yields:
            Each page of member IDs
        """
        async for members in self._paginate(
            "GET",
            "conversations.members",
            params={
                "channel": channel_id,
                "limit": 1000  # Max allowed by Slack
            },
            items_key="members"
        ):
            yield members

    async def close(self):
        """Close the HTTP client session."""
        await self.client.aclose()
