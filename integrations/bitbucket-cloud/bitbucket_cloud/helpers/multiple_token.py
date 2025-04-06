import time
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
import asyncio
from loguru import logger
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.base_client import BitbucketBaseClient
from port_ocean.context.ocean import ocean
from httpx import HTTPError
from http import HTTPStatus


class BitbucketClientManager:
    """
    Manages multiple BitbucketClient instances and rotates through them using RollingWindowLimiter.
    """

    def __init__(
        self,
        workspace: str,
        host: str,
        limit_per_client: int,
        window: float,
    ) -> None:
        self.workspace = workspace
        self.host = host
        self.clients: dict[str, tuple[BitbucketClient, RollingWindowLimiter]] = {}
        self.client_queue: asyncio.PriorityQueue[
            Tuple[float, str, BitbucketClient, RollingWindowLimiter]
        ] = asyncio.PriorityQueue()
        self.limit_per_client = limit_per_client
        self.window = window

        self._initialize_clients()

        logger.info(
            f"Initialized BitbucketClientManager with {len(self.clients)} clients."
        )

    def _initialize_clients(self) -> None:
        """
        Parses credentials from environment and initializes clients and their limiters.
        """
        parsed_credentials = self._parse_credentials()
        for client_id, cred in parsed_credentials.items():
            self.add_client(client_id, cred)

        # After all clients are created, add alternative base clients to each client
        self._add_alternative_base_clients()

    def _add_alternative_base_clients(self) -> None:
        """
        Add alternative base clients to each BitbucketClient instance.
        This allows each client to rotate between different authentication methods.
        """
        # Create a list of all base clients and their limiters
        base_clients_with_limiters: list[
            tuple[BitbucketBaseClient, RollingWindowLimiter]
        ] = []
        base_clients_with_limiters.extend(
            (client.base_client, limiter)
            for client_id, (client, limiter) in self.clients.items()
        )
        # Add alternative base clients to each client
        for client_id, (client, _) in self.clients.items():
            for base_client, limiter in base_clients_with_limiters:
                if base_client != client.base_client:
                    client.add_alternative_base_client(base_client, limiter)

        logger.info("Added alternative base clients to all BitbucketClient instances")

    def _parse_credentials(
        self,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Parse credentials from environment variables.
        Each credential can be either a workspace token or a username::app_password combination.
        """
        parsed_credentials = {}

        # Get lists of credentials from environment, handling None values
        usernames = [
            u.strip()
            for u in (ocean.integration_config.get("bitbucket_username") or "").split(
                ","
            )
            if u.strip()
        ]
        app_passwords = [
            p.strip()
            for p in (
                ocean.integration_config.get("bitbucket_app_password") or ""
            ).split(",")
            if p.strip()
        ]
        workspace_tokens = [
            t.strip()
            for t in (
                ocean.integration_config.get("bitbucket_workspace_token") or ""
            ).split(",")
            if t.strip()
        ]

        # Handle workspace tokens first
        for index, token in enumerate(workspace_tokens):
            client_id = f"client_{index}"
            parsed_credentials[client_id] = {
                "username": None,
                "app_password": None,
                "workspace_token": token,
            }

        # Then handle username + app password combinations
        start_index = len(workspace_tokens)
        for index, (username, app_password) in enumerate(zip(usernames, app_passwords)):
            client_id = f"client_{start_index + index}"
            parsed_credentials[client_id] = {
                "username": username,
                "app_password": app_password,
                "workspace_token": None,
            }

        return parsed_credentials

    def add_client(self, client_id: str, cred: Dict[str, Optional[str]]) -> None:
        """
        Dynamically add a new client to the manager.
        """
        if client_id in self.clients:
            raise ValueError(f"Client with ID '{client_id}' already exists.")

        # Create a BitbucketBaseClient instance first
        base_client = BitbucketBaseClient(
            workspace=self.workspace,
            host=self.host,
            username=cred.get("username"),
            app_password=cred.get("app_password"),
            workspace_token=cred.get("workspace_token"),
        )

        # Create a new rate limiter for this client
        limiter = RollingWindowLimiter(limit=self.limit_per_client, window=self.window)
        # Then create a BitbucketClient with the base client and client_id
        client = BitbucketClient(base_client=base_client, client_id=client_id)
        client.current_limiter = limiter

        # Store the client and limiter in the clients dictionary
        self.clients[client_id] = (client, limiter)
        self.client_queue.put_nowait((0.0, client_id, client, limiter))

        logger.info(f"Added new client '{client_id}' to the manager.")

    async def _get_next_client(
        self,
    ) -> Tuple[str, BitbucketClient, RollingWindowLimiter]:
        """
        Get the next available client from the queue.
        """
        # Keep track of which clients have been tried
        tried_clients = set()

        while True:
            availability, client_id, client, limiter = await self.client_queue.get()
            now = time.monotonic()

            if availability <= now:
                if limiter.has_capacity():
                    return client_id, client, limiter
                # If no capacity, put it back in queue with next available time
                next_available = limiter.next_available_time()
                self.client_queue.put_nowait(
                    (next_available, client_id, client, limiter)
                )
                logger.info(
                    f"Client {client_id} has no capacity, next available at {next_available}"
                )

                # Add the client to the tried set
                tried_clients.add(client_id)

                # If we've tried all clients and none have capacity, find the earliest available one
                if len(tried_clients) == len(self.clients):
                    # Find the earliest available time among all clients
                    earliest_available = float("inf")
                    earliest_client = None
                    earliest_client_id = None

                    for client_id, (client, limiter) in self.clients.items():
                        if limiter.has_capacity():
                            return client_id, client, limiter
                        next_available = limiter.next_available_time()
                        if next_available < earliest_available:
                            earliest_available = next_available
                            earliest_client = client
                            earliest_client_id = client_id

                    if earliest_client:
                        logger.info(
                            f"All clients have no capacity, queueing on first available client at {earliest_available}"
                        )
                        await asyncio.sleep(earliest_available - now)
                        # We know earliest_client_id is not None at this point
                        assert earliest_client_id is not None
                        return (
                            earliest_client_id,
                            earliest_client,
                            self.clients[earliest_client_id][1],
                        )
            else:
                self.client_queue.put_nowait((availability, client_id, client, limiter))

    async def execute_request(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """
        Execute a method on a rotated BitbucketClient instance with precise rate limiting.
        Will rotate to another client only on rate limit (429) errors.
        """
        logger.info(
            f"Executing request {method_name} with args {args} and kwargs {kwargs}"
        )

        while True:
            try:
                client_id, client, limiter = await self._get_next_client()
                logger.info(f"Using client {client_id} with limiter {limiter}")
                client.current_limiter = limiter
                client_method = getattr(client, method_name)

                # The rate limiter will handle the timing of requests
                async for item in client_method(*args, **kwargs):
                    logger.info(f"Yielding item from client {client_id}")
                    yield item
                break  # Successfully completed, exit the loop
            except asyncio.CancelledError:
                logger.warning("Operation cancelled, cleaning up")
                raise
            except HTTPError as e:
                if (
                    hasattr(e, "response")
                    and e.response
                    and e.response.status_code == HTTPStatus.TOO_MANY_REQUESTS
                ):
                    logger.warning(
                        f"Rate limit hit for client {client_id}, rotating to next client"
                    )
                    continue  # Try next client
                logger.error(f"Error while making request with {client_id}: {str(e)}")
                raise  # Re-raise non-rate-limit errors
            except Exception as e:
                logger.error(f"Error while making request with {client_id}: {str(e)}")
                raise
