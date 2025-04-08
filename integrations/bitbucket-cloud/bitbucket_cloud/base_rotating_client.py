import asyncio
import time
from typing import Optional, Tuple, List
from loguru import logger
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter


class BaseRotatingClient:
    """
    Base class for clients that need to rotate between multiple base clients
    to handle rate limiting.
    """

    def __init__(self):
        """Initialize the rotating client."""
        self.base_client: Optional[BitbucketBaseClient] = None
        self.current_limiter: Optional[RollingWindowLimiter] = None
        self.client_id: Optional[str] = None
        self.base_client_priority_queue: Optional[asyncio.PriorityQueue] = None
        self.base_url: str = ""
        self.workspace: str = ""

    def set_base_client(self, base_client: BitbucketBaseClient) -> None:
        """
        Set the base client and update related attributes.

        Args:
            base_client: The base client to set.
        """
        self.base_client = base_client
        self.base_url = base_client.base_url
        self.workspace = base_client.workspace

    async def _get_next_client_from_queue(
        self,
    ) -> Tuple[
        Optional[str], Optional[BitbucketBaseClient], Optional[RollingWindowLimiter]
    ]:
        """
        Get the next available client from the priority queue.

        Returns:
            Tuple containing the client ID, base client, and limiter.
            If no client is available, returns (None, None, None).
        """
        if not self.base_client_priority_queue:
            logger.warning("No priority queue set for client rotation")
            return None, None, None

        tried_clients = set()
        all_clients = []
        now = time.monotonic()

        while True:
            try:
                # Get next client from queue
                availability, client_id, base_client, limiter = (
                    await self.base_client_priority_queue.get()
                )
                all_clients.append((availability, client_id, base_client, limiter))

                # Check if client is available and has capacity
                if availability <= now and limiter.has_capacity():
                    # Put back other clients
                    for a, cid, bc, l in all_clients:
                        if cid != client_id:
                            self.base_client_priority_queue.put_nowait((a, cid, bc, l))
                    return client_id, base_client, limiter

                # Handle client with no capacity
                if availability <= now:
                    # Update availability and put back in queue
                    next_available = limiter.next_available_time()
                    self.base_client_priority_queue.put_nowait(
                        (next_available, client_id, base_client, limiter)
                    )
                    logger.info(
                        f"Client {client_id} has no capacity, next available at {next_available}"
                    )

                    tried_clients.add(client_id)

                    # If we've tried all clients and none have capacity, find earliest available
                    if len(tried_clients) == len(all_clients):
                        return await self._find_earliest_available_client(
                            all_clients, now
                        )
                else:
                    # Client not yet available, put back in queue
                    self.base_client_priority_queue.put_nowait(
                        (availability, client_id, base_client, limiter)
                    )
            except asyncio.QueueEmpty:
                logger.warning("Client queue is empty")
                return None, None, None

    async def _find_earliest_available_client(
        self,
        all_clients: List[Tuple[float, str, BitbucketBaseClient, RollingWindowLimiter]],
        now: float,
    ) -> Tuple[
        Optional[str], Optional[BitbucketBaseClient], Optional[RollingWindowLimiter]
    ]:
        """
        Find the earliest available client when all clients have been tried.

        Args:
            all_clients: List of all clients.
            now: The current time.

        Returns:
            Tuple containing the client ID, base client, and limiter.
        """
        # First check if any client has capacity now
        for a, cid, bc, l in all_clients:
            if l.has_capacity():
                # Put back all clients
                for a2, cid2, bc2, l2 in all_clients:
                    self.base_client_priority_queue.put_nowait((a2, cid2, bc2, l2))
                return cid, bc, l

        # If no client has capacity, find earliest available
        earliest_available = float("inf")
        earliest_base_client = None
        earliest_client_id = None
        earliest_limiter = None

        for a, cid, bc, l in all_clients:
            next_available = l.next_available_time()
            if next_available < earliest_available:
                earliest_available = next_available
                earliest_base_client = bc
                earliest_client_id = cid
                earliest_limiter = l

        if earliest_base_client:
            logger.info(
                f"All clients have no capacity, queueing on first available client at {earliest_available}"
            )
            await asyncio.sleep(earliest_available - now)
            # Put back all clients
            for a, cid, bc, l in all_clients:
                self.base_client_priority_queue.put_nowait((a, cid, bc, l))
            return earliest_client_id, earliest_base_client, earliest_limiter

        # If we get here, something went wrong
        for a, cid, bc, l in all_clients:
            self.base_client_priority_queue.put_nowait((a, cid, bc, l))
        return None, None, None

    async def _ensure_client_available(self) -> None:
        """
        Ensure that a base client and rate limiter are available.
        If the current client/limiter pair doesn't have capacity, find another available pair.
        If no client has immediate capacity, wait for the first available limiter.
        """
        # If we don't have a client or limiter, get one from the queue
        if self.base_client is None or self.current_limiter is None:
            logger.info(
                "No base client or limiter available, attempting to get from queue"
            )
            client_id, base_client, limiter = await self._get_next_client_from_queue()
            if base_client and limiter:
                self.base_client = base_client
                self.current_limiter = limiter
                self.client_id = client_id
                logger.info(f"Set base client {client_id} and limiter {id(limiter)}")
            else:
                logger.error("Failed to get base client and limiter from queue")
                raise RuntimeError("No available base client and limiter")

        # Check if the current client has capacity
        if not self.current_limiter.has_capacity():
            logger.info(
                f"Current client {self.client_id} has no capacity, rotating to next client"
            )
            await self._rotate_base_client()

    async def _rotate_base_client(self) -> None:
        """
        Rotate to the next available base client.
        This method will find a client with capacity or wait for the earliest available one.
        """
        logger.info("Rotating to next base client")

        # Get the next available client
        client_id, base_client, limiter = await self._get_next_client_from_queue()

        if base_client and limiter:
            # Update the current client and limiter
            self.base_client = base_client
            self.current_limiter = limiter
            self.client_id = client_id
            logger.info(f"Rotated to base client {client_id} and limiter {id(limiter)}")
        else:
            logger.error("Failed to rotate to next base client")
            raise RuntimeError("No available base client and limiter")
