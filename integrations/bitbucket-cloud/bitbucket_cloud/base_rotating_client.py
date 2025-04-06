from typing import Optional, Dict, Tuple, Set
import asyncio
import time
from loguru import logger
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter


class BaseRotatingClient:
    """
    Base class for clients that can rotate between multiple base clients.
    Provides functionality to manage and rotate between alternative base clients.
    """

    def __init__(self, base_client: BitbucketBaseClient):
        """
        Initialize with a base client.

        Args:
            base_client: The initial base client to use.
        """
        self.base_client = base_client
        self.base_client_queue: asyncio.Queue[BitbucketBaseClient] = asyncio.Queue()
        self.base_client_queue.put_nowait(base_client)

        # Package base clients with their rate limiters
        self.client_packages: Dict[BitbucketBaseClient, RollingWindowLimiter] = {}
        self.current_limiter: Optional[RollingWindowLimiter] = None

        # Track which base clients have been tried in the current rotation cycle
        self._tried_base_clients: Set[BitbucketBaseClient] = set()

    def add_alternative_base_client(
        self,
        base_client: BitbucketBaseClient,
        limiter: RollingWindowLimiter,
    ) -> None:
        """
        Add an alternative base client to the rotation queue.

        Args:
            base_client: The alternative base client to add.
            limiter: The rate limiter associated with this base client.
        """
        if base_client not in self.client_packages:
            self.base_client_queue.put_nowait(base_client)
            self.client_packages[base_client] = limiter
            logger.info("Added alternative base client to rotation queue")
        else:
            logger.info("Base client already in rotation queue")

    async def _rotate_base_client(self) -> None:
        """
        Rotate to the next available base client using the queue.
        Also updates the current rate limiter.
        """
        if self.base_client_queue.qsize() <= 1:
            logger.warning("No alternative base clients available for rotation")
            return

        # Get the next base client from the queue
        next_base_client = await self.base_client_queue.get()
        # Put the current base client back in the queue
        self.base_client_queue.put_nowait(self.base_client)
        # Update the current base client
        self.base_client = next_base_client

        # Update the current rate limiter
        self.current_limiter = self.client_packages.get(next_base_client)  # type: ignore
        if self.current_limiter is None:
            logger.warning("No rate limiter found for the next base client")
        limiter_id = id(self.current_limiter) if self.current_limiter else None
        logger.info(
            f"Rotated to alternative base client with rate limiter ID: {limiter_id}"
        )

        # Add the base client to the tried set
        self._tried_base_clients.add(next_base_client)

    def has_tried_all_clients(self) -> bool:
        """
        Check if all base clients have been tried in the current rotation cycle.

        Returns:
            bool: True if all base clients have been tried, False otherwise.
        """
        return len(self._tried_base_clients) == len(self.client_packages)

    def reset_tried_clients(self) -> None:
        """
        Reset the set of tried base clients.
        """
        self._tried_base_clients.clear()

    def get_earliest_available_client(
        self,
    ) -> Tuple[Optional[BitbucketBaseClient], float]:
        """
        Find the earliest available client and its availability time.

        Returns:
            Tuple containing the earliest available client and its availability time.
            If no client is available, returns (None, float('inf')).
        """
        earliest_available = float("inf")
        earliest_base_client = None

        for base_client, limiter in self.client_packages.items():
            if limiter and limiter.has_capacity():
                # If any client has capacity, return it immediately
                return base_client, 0.0
            else:
                next_available = (
                    limiter.next_available_time() if limiter else float("inf")
                )
                if next_available < earliest_available:
                    earliest_available = next_available
                    earliest_base_client = base_client

        return earliest_base_client, earliest_available

    async def _ensure_client_available(self) -> None:
        """
        Ensure that a client with capacity is available.
        If the current client has no capacity, try to find another one.
        If all clients have been tried, wait for the earliest available one.
        """
        if self.current_limiter and not self.current_limiter.has_capacity():
            # If we've tried all clients, find the earliest available one
            if self.has_tried_all_clients():
                earliest_client, earliest_time = self.get_earliest_available_client()

                if earliest_client:
                    logger.info(
                        f"All base clients have no capacity, queueing on first available client at {earliest_time}"
                    )
                    # Wait until the earliest available time
                    await asyncio.sleep(earliest_time - time.monotonic())
                    # Set the earliest available base client
                    self.base_client = earliest_client
                    self.current_limiter = self.client_packages.get(earliest_client)
                    # Reset the tried set
                    self.reset_tried_clients()
                else:
                    # If no client has capacity, rotate to the next one
                    await self._rotate_base_client()
            else:
                # If we haven't tried all clients yet, rotate to the next one
                await self._rotate_base_client()
