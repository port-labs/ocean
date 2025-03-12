from typing import Union, Tuple, List, Optional
from loguru import logger
from contextlib import asynccontextmanager
from httpx import AsyncClient, Timeout
from port_ocean.utils import http_async_client

import base64
from .rate_limiter import RollingWindowLimiter
import time

TIMEOUT = 30
TokenType = Union[str, Tuple[str, str]]


class TokenClient:
    """Represents a client with its associated token and rate limiter."""

    def __init__(
        self,
        token: TokenType,
        base_url: str,
        requests_per_hour: int,
        window: float,
        timeout: int = TIMEOUT,
    ):
        self.token = token
        self.client = http_async_client
        self.client.timeout = Timeout(timeout)
        self.client.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        self.base_url = base_url
        self._setup_auth()

        self.rate_limiter = RollingWindowLimiter(
            limit=requests_per_hour, window=window, logger=logger
        )

    def _setup_auth(self) -> None:
        """Setup authentication headers based on token type."""
        if isinstance(self.token, str):
            self.client.headers["Authorization"] = f"Bearer {self.token}"
        else:
            username, app_password = self.token
            auth = base64.b64encode(f"{username}:{app_password}".encode()).decode()
            self.client.headers["Authorization"] = f"Basic {auth}"

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()


class MultiTokenBitbucketClient:
    """Base client that supports multiple authentication tokens with rate limiting."""

    def __init__(
        self,
        credentials: List[TokenType],
        requests_per_hour: int = 1000,
        window: int = 3600,
    ) -> None:
        """Initialize with multiple credentials."""
        if not credentials:
            raise ValueError("At least one credential is required")

        self.base_url = "https://api.bitbucket.org/2.0"
        self.token_clients = [
            TokenClient(
                token=token,
                base_url=self.base_url,
                requests_per_hour=requests_per_hour,
                window=window,
            )
            for token in credentials
        ]
        self.current_client_index = 0

    def get_current_client(self) -> TokenClient:
        """Get the current active client."""
        return self.token_clients[self.current_client_index]

    def _rotate_client(self) -> None:
        """Rotate to next available client."""
        if len(self.token_clients) <= 1:
            return
        self.current_client_index = (self.current_client_index + 1) % len(
            self.token_clients
        )
        logger.debug("Rotated to next client")

    async def _find_available_client(self) -> Optional[TokenClient]:
        """Find a client that can accept requests immediately."""
        original_index = self.current_client_index

        # Try each client once
        for _ in range(len(self.token_clients)):
            current_client = self.get_current_client()

            # Check if this client's rate limiter has immediate capacity
            if (
                len(current_client.rate_limiter._timestamps)
                < current_client.rate_limiter.limit
            ):
                return current_client

            self._rotate_client()

        # If no available client found, revert to original
        self.current_client_index = original_index
        return None

    @asynccontextmanager
    async def rate_limit(self, endpoint: str):
        """Context manager for rate limiting repository endpoints."""
        if not endpoint.startswith("repositories/"):
            yield False
            return

        try:
            # First try to find a client with immediate capacity
            available_client = await self._find_available_client()

            if available_client:
                # Use the available client's rate limiter without waiting
                self.current_client_index = self.token_clients.index(available_client)
                logger.debug(f"Using available client for immediate request")
                async with available_client.rate_limiter:
                    yield False
            else:
                # No immediately available client, find the one that will be available soonest
                min_wait_time = float("inf")
                best_client = None

                for client in self.token_clients:
                    if client.rate_limiter._timestamps:
                        # Calculate when this client's oldest request expires
                        oldest = client.rate_limiter._timestamps[0]
                        wait_time = (
                            oldest + client.rate_limiter.window - time.monotonic()
                        )
                        if wait_time < min_wait_time:
                            min_wait_time = wait_time
                            best_client = client

                if best_client:
                    # Switch to the client that will be available soonest
                    self.current_client_index = self.token_clients.index(best_client)
                    logger.debug(
                        f"Switching to client with shortest wait time: {min_wait_time:.2f}s"
                    )

                current_client = self.get_current_client()
                logger.debug(
                    f"All clients at capacity, waiting for next available slot"
                )
                async with current_client.rate_limiter:
                    yield True

        except Exception as e:
            logger.error(f"Error in rate limiting: {str(e)}")
            # Make sure to re-raise the exception
            raise
            # No yield here, ensuring the generator stops

    async def close(self) -> None:
        """Close all clients."""
        for token_client in self.token_clients:
            await token_client.close()
