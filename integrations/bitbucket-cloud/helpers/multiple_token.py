import time
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
import asyncio
from loguru import logger
from helpers.rate_limiter import RollingWindowLimiter
from client import BitbucketClient


class BitbucketClientManager:
    """
    Manages multiple BitbucketClient instances and rotates through them using RollingWindowLimiter.
    """

    def __init__(
        self,
        workspace: str,
        host: str,
        credentials: str,
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

        self._initialize_clients(credentials)

        logger.info(
            f"Initialized BitbucketClientManager with {len(self.clients)} clients."
        )

    def _initialize_clients(self, credentials: str) -> None:
        """
        Parses credentials and initializes clients and their limiters.
        """
        parsed_credentials = self._parse_credentials(credentials)
        for client_id, cred in parsed_credentials.items():
            self.add_client(client_id, cred)

    def _parse_credentials(
        self, credentials: str
    ) -> Dict[str, Dict[str, Optional[str]]]:
        parsed_credentials = {}
        for index, cred in enumerate(credentials.split(",")):
            client_id = f"client_{index}"
            if "::" in cred:
                username, app_password = cred.split("::", 1)
                parsed_credentials[client_id] = {
                    "username": username,
                    "app_password": app_password,
                    "workspace_token": None,
                }
            else:
                parsed_credentials[client_id] = {
                    "username": None,
                    "app_password": None,
                    "workspace_token": cred,
                }
        return parsed_credentials

    def add_client(self, client_id: str, cred: Dict[str, Optional[str]]) -> None:
        """
        Dynamically add a new client to the manager.
        """
        if client_id in self.clients:
            raise ValueError(f"Client with ID '{client_id}' already exists.")

        client = BitbucketClient(
            workspace=self.workspace,
            host=self.host,
            username=cred.get("username"),
            app_password=cred.get("app_password"),
            workspace_token=cred.get("workspace_token"),
        )
        limiter = RollingWindowLimiter(limit=self.limit_per_client, window=self.window)

        self.clients[client_id] = (client, limiter)
        self.client_queue.put_nowait((0.0, client_id, client, limiter))

        logger.info(f"Added new client '{client_id}' to the manager.")

    async def _rotate_client(self) -> Tuple[str, BitbucketClient, RollingWindowLimiter]:
        """
        Efficiently rotate clients based on availability tracking.
        """
        while True:
            availability, client_id, client, limiter = await self.client_queue.get()
            now = time.monotonic()

            if availability <= now and limiter.has_capacity():
                return client_id, client, limiter

            next_available = limiter.next_available_time()
            self.client_queue.put_nowait((next_available, client_id, client, limiter))
            await asyncio.sleep(max(0, next_available - now))

    async def execute_request(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """
        Execute a method on a rotated BitbucketClient instance with precise rate limiting.

        If the client method is an async generator, yield items as they are produced.
        Will rotate to another client only on rate limit (429) errors, raises all other exceptions.
        """
        while True:
            client_id, client, limiter = await self._rotate_client()

            try:
                async with limiter:
                    client_method = getattr(client, method_name)
                    async for item in client_method(*args, **kwargs):
                        yield item
                    break
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 429:
                    logger.warning(
                        f"Rate limit hit for client {client_id}, rotating to next client"
                    )
                    continue
                logger.error(f"Error while making request with {client_id}: {e}")
                raise
