import asyncio
import time
from typing import Tuple, List, Any, Set
from loguru import logger
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.helpers.exceptions import ClassAttributeNotInitializedError


class BaseRotatingClient:
    """
    Base class for clients that need to rotate between multiple base clients
    to handle rate limiting.
    """

    def __init__(self) -> None:
        """Initialize the rotating client."""
        self.base_client: BitbucketBaseClient | None = None
        self.current_limiter: RollingWindowLimiter | None = None
        self.client_id: str | None = None
        self.base_client_priority_queue: (
            asyncio.PriorityQueue[
                Tuple[float, str, BitbucketBaseClient, RollingWindowLimiter]
            ]
            | None
        ) = None
        self.base_url: str | None = None
        self.workspace: str | None = None

    def set_base_client(self, base_client: BitbucketBaseClient) -> None:
        """
        Set the base client and update related attributes.

        Args:
            base_client: The base client to set.
        """
        self.base_client = base_client
        self.base_url = base_client.base_url
        self.workspace = base_client.workspace

    def _update_client_state(
        self,
        client_id: str,
        base_client: BitbucketBaseClient,
        limiter: RollingWindowLimiter,
    ) -> None:
        """
        Update the client state with new client information.

        Args:
            client_id: The ID of the client.
            base_client: The base client to set.
            limiter: The rate limiter for the client.
        """
        self.base_client = base_client
        self.current_limiter = limiter
        self.client_id = client_id
        logger.info(f"Set base client {client_id} and limiter {id(limiter)}")

    def _put_clients_back_in_queue(self, all_clients: List[Tuple[Any, ...]]) -> None:
        """
        Put all clients back in the priority queue.

        Args:
            all_clients: List of client tuples to put back in the queue.
        """
        queue = self.base_client_priority_queue
        if queue is None:
            logger.warning("Cannot put clients back in queue: queue is None")
            return

        for client_tuple in all_clients:
            queue.put_nowait(client_tuple)

    def _handle_client_with_capacity(
        self,
        client_id: str,
        base_client: BitbucketBaseClient,
        limiter: RollingWindowLimiter,
        all_clients: List[Tuple[Any, ...]],
    ) -> Tuple[str, BitbucketBaseClient, RollingWindowLimiter]:
        """
        Handle a client that has capacity.

        Args:
            client_id: The ID of the client.
            base_client: The base client.
            limiter: The rate limiter.
            all_clients: List of all clients.

        Returns:
            Tuple containing the client ID, base client, and limiter.
        """
        # Put back other clients
        for (
            avail_time,
            queued_client_id,
            queued_base_client,
            rate_limiter,
        ) in all_clients:
            if queued_client_id != client_id and self.base_client_priority_queue:
                self.base_client_priority_queue.put_nowait(
                    (
                        avail_time,
                        queued_client_id,
                        queued_base_client,
                        rate_limiter,
                    )
                )
        return client_id, base_client, limiter

    async def _handle_client_without_capacity(
        self,
        client_id: str,
        base_client: BitbucketBaseClient,
        limiter: RollingWindowLimiter,
        tried_clients: Set[str],
        all_clients: List[Tuple[Any, ...]],
        current_time: float,
    ) -> (
        Tuple[str | None, BitbucketBaseClient | None, RollingWindowLimiter | None]
        | None
    ):
        """
        Handle a client that doesn't have capacity.

        Args:
            client_id: The ID of the client.
            base_client: The base client.
            limiter: The rate limiter.
            tried_clients: Set of clients that have been tried.
            all_clients: List of all clients.
            current_time: The current time.

        Returns:
            Tuple containing the client ID, base client, and limiter, or None if no client is available.
        """
        # Update availability and put back in queue
        next_available_time = limiter.next_available_time()

        if self.base_client_priority_queue is None:
            logger.warning("Cannot put client back in queue: queue is None")
            raise ClassAttributeNotInitializedError("Queue is not initialized")

        self.base_client_priority_queue.put_nowait(
            (next_available_time, client_id, base_client, limiter)
        )
        logger.info(
            f"Client {client_id} has no capacity, next available at {next_available_time}"
        )

        tried_clients.add(client_id)

        # If we've tried all clients and none have capacity, find earliest available
        if len(tried_clients) == len(all_clients):
            return await self._find_earliest_available_client(all_clients, current_time)
        return None

    async def _get_next_client_from_queue(
        self,
    ) -> Tuple[str | None, BitbucketBaseClient | None, RollingWindowLimiter | None]:
        """
        Get the next available client from the priority queue.

        Returns:
            Tuple containing the client ID, base client, and limiter.
            If no client is available, returns (None, None, None).
        """
        if not self.base_client_priority_queue:
            logger.warning("No priority queue set for client rotation")
            return None, None, None

        tried_clients: Set[str] = set()
        all_clients = []
        current_time = time.monotonic()

        while True:
            try:
                # Get next client from queue
                availability_time, client_id, base_client, limiter = (
                    await self.base_client_priority_queue.get()
                )
                all_clients.append((availability_time, client_id, base_client, limiter))

                # Check if client has capacity, regardless of availability time
                if limiter.has_capacity():
                    return self._handle_client_with_capacity(
                        client_id, base_client, limiter, all_clients
                    )

                # If client has no capacity, add to tried clients
                tried_clients.add(client_id)

                # If we've tried all clients and none have capacity, find earliest available
                if len(tried_clients) == len(all_clients):
                    return await self._find_earliest_available_client(
                        all_clients, current_time
                    )

                # Put the client back in the queue
                self.base_client_priority_queue.put_nowait(
                    (availability_time, client_id, base_client, limiter)
                )
            except asyncio.QueueEmpty:
                logger.warning("Client queue is empty")
                return None, None, None

    async def _find_earliest_available_client(
        self,
        all_clients: List[Tuple[float, str, BitbucketBaseClient, RollingWindowLimiter]],
        current_time: float,
    ) -> Tuple[str | None, BitbucketBaseClient | None, RollingWindowLimiter | None]:
        """
        Find the earliest available client when all clients have been tried.

        Args:
            all_clients: List of all clients.
            current_time: The current time.

        Returns:
            Tuple containing the client ID, base client, and limiter.
        """
        # First check if any client has capacity now
        for avail_time, client_id, base_client, limiter in all_clients:
            if limiter.has_capacity():
                # Put back all clients
                self._put_clients_back_in_queue(all_clients)
                return client_id, base_client, limiter

        # If no client has capacity, find earliest available
        earliest_available_time = float("inf")
        earliest_base_client = None
        earliest_client_id = None
        earliest_limiter = None

        for avail_time, client_id, base_client, limiter in all_clients:
            next_available_time = limiter.next_available_time()
            if next_available_time < earliest_available_time:
                earliest_available_time = next_available_time
                earliest_base_client = base_client
                earliest_client_id = client_id
                earliest_limiter = limiter

        if earliest_base_client:
            logger.info(
                f"All clients have no capacity, selecting client {earliest_client_id} which will be available at {earliest_available_time}"
            )
            # Put back all clients
            self._put_clients_back_in_queue(all_clients)
            return earliest_client_id, earliest_base_client, earliest_limiter

        # If we get here, something went wrong
        self._put_clients_back_in_queue(all_clients)
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
            if base_client and limiter and client_id:
                self._update_client_state(client_id, base_client, limiter)
            else:
                logger.error("Failed to get base client and limiter from queue")
                raise ClassAttributeNotInitializedError(
                    "No available base client and limiter"
                )

        # Check if the current client has capacity
        if self.current_limiter is None:
            logger.warning("Current limiter is None, cannot check capacity")
            await self._rotate_base_client()
            return

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

        if base_client and limiter and client_id:
            # Update the current client and limiter
            self._update_client_state(client_id, base_client, limiter)
        else:
            logger.error("Failed to rotate to next base client")
            raise ClassAttributeNotInitializedError(
                "No available base client and limiter"
            )
