import asyncio
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from loguru import logger
from port_ocean.utils import http_async_client

from .auth import SpaceliftAuthenticator, AuthenticationError


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class SpaceliftBaseClient:
    """Base client for making GraphQL requests to Spacelift API."""

    def __init__(self) -> None:
        self.http_client = http_async_client
        self.authenticator = SpaceliftAuthenticator()
        self._rate_limit_retry_after: Optional[datetime] = None

    async def initialize(self) -> None:
        """Initialize the client and authenticate."""
        logger.info("Initializing Spacelift client")
        await self.authenticator.ensure_authenticated()

        await self._test_connection()

        logger.success("Spacelift client initialized successfully")

    async def _handle_rate_limit(self, response: Any) -> None:
        """Handle rate limiting with retry logic."""
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            try:
                retry_seconds = int(retry_after)
            except ValueError:
                retry_seconds = 60

            self._rate_limit_retry_after = datetime.now() + timedelta(
                seconds=retry_seconds
            )
            logger.warning(
                f"Rate limit exceeded. Waiting {retry_seconds} seconds before retry"
            )
            await asyncio.sleep(retry_seconds)
            raise RateLimitError(
                f"Rate limit exceeded. Retry after {retry_seconds} seconds"
            )

    async def make_graphql_request(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make a GraphQL request with authentication and rate limiting."""
        token = await self.authenticator.ensure_authenticated()

        if (
            self._rate_limit_retry_after
            and datetime.now() < self._rate_limit_retry_after
        ):
            wait_time = (self._rate_limit_retry_after - datetime.now()).total_seconds()
            logger.info(f"Still in rate limit period. Waiting {wait_time:.1f} seconds")
            await asyncio.sleep(wait_time)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        request_data: Dict[str, Any] = {"query": query}
        if variables:
            request_data["variables"] = variables

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Making GraphQL request (attempt {attempt + 1}/{max_retries})"
                )

                api_endpoint = self.authenticator.get_api_endpoint()
                response = await self.http_client.request(
                    method="POST",
                    url=api_endpoint,
                    json=request_data,
                    headers=headers,
                )

                if response.status_code == 401:
                    # Token might have expired, try to re-authenticate
                    logger.warning("Received 401, attempting to re-authenticate")
                    self.authenticator.invalidate_token()
                    token = await self.authenticator.ensure_authenticated()
                    headers["Authorization"] = f"Bearer {token}"
                    continue

                if response.status_code == 429:
                    await self._handle_rate_limit(response)
                    continue

                if response.is_error:
                    logger.error(
                        f"GraphQL request failed: {response.status_code} - {response.text}"
                    )
                    if attempt == max_retries - 1:
                        raise Exception(
                            f"GraphQL request failed: {response.status_code} - {response.text}"
                        )
                    await asyncio.sleep(2**attempt)
                    continue

                data = response.json()

                if "errors" in data:
                    logger.error(f"GraphQL errors: {data['errors']}")

                    error_messages = [
                        error.get("message", "").lower() for error in data["errors"]
                    ]
                    if any(
                        "unauthorized" in msg
                        or "forbidden" in msg
                        or "access denied" in msg
                        for msg in error_messages
                    ):
                        raise AuthenticationError(
                            f"Authorization failed: {data['errors']}"
                        )

                    raise Exception(f"GraphQL errors: {data['errors']}")

                return data

            except RateLimitError:
                if attempt == max_retries - 1:
                    raise
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    f"Request attempt {attempt + 1} failed: {e}. Retrying..."
                )
                await asyncio.sleep(2**attempt)

        raise Exception("All retry attempts failed")

    async def _test_connection(self) -> None:
        """Test the connection with a simple query."""
        try:
            query = """
            query TestConnection {
                stacks {
                    id
                }
            }
            """

            data = await self.make_graphql_request(query)
            stacks = (
                data["data"].get("stacks", []) if data.get("data") else []
            )  # Handle None case
            logger.info(
                f"Successfully connected to Spacelift API - found {len(stacks)} stacks"
            )

        except Exception as e:
            logger.warning(f"Connection test failed, but proceeding: {e}")
