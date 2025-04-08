from typing import Any, AsyncGenerator, Dict, Optional, Tuple
import asyncio
from loguru import logger
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.base_client import BitbucketBaseClient
from port_ocean.context.ocean import ocean


class BitbucketClientManager:
    """
    Manages a single BitbucketClient instance with multiple BitbucketBaseClient instances,
    each with its own RollingWindowLimiter for rate limiting.
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
        self.limit_per_client = limit_per_client
        self.window = window
        self.client: Optional[BitbucketClient] = None
        self.base_clients: Dict[str, BitbucketBaseClient] = {}
        self.limiters: Dict[str, RollingWindowLimiter] = {}
        self.client_queue: asyncio.PriorityQueue[
            Tuple[float, str, BitbucketBaseClient, RollingWindowLimiter]
        ] = asyncio.PriorityQueue()

        self._initialize_clients()

        logger.info(
            f"Initialized BitbucketClientManager with {len(self.base_clients)} base clients."
        )

    def _initialize_clients(self) -> None:
        """
        Parses credentials from environment and initializes base clients and their limiters.
        """
        parsed_credentials = self._parse_credentials()
        for client_id, cred in parsed_credentials.items():
            self.add_base_client(client_id, cred)

        # Create a single BitbucketClient with the first base client
        if self.base_clients:
            first_client_id = next(iter(self.base_clients))
            self.client = BitbucketClient()
            self.client.set_base_client(self.base_clients[first_client_id])
            self.client.current_limiter = self.limiters[first_client_id]
            self.client.client_id = first_client_id
            # Pass the priority queue to the client
            self.client.base_client_priority_queue = self.client_queue
        logger.info("Created single BitbucketClient with multiple base clients")

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

    def add_base_client(self, client_id: str, cred: Dict[str, Optional[str]]) -> None:
        """
        Dynamically add a new base client to the manager.
        """
        base_client = BitbucketBaseClient(
            workspace=self.workspace,
            host=self.host,
            username=cred.get("username"),
            app_password=cred.get("app_password"),
            workspace_token=cred.get("workspace_token"),
        )
        limiter = RollingWindowLimiter(limit=self.limit_per_client, window=self.window)
        self.base_clients[client_id] = base_client
        self.limiters[client_id] = limiter
        self.client_queue.put_nowait((0.0, client_id, base_client, limiter))
        logger.info(f"Added new base client '{client_id}' to the manager.")

    async def execute_request(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """
        Execute a method on the BitbucketClient instance with precise rate limiting.
        Will rotate to another base client only on rate limit (429) errors.
        """
        logger.info(
            f"Executing request {method_name} with args {args} and kwargs {kwargs}"
        )

        while True:
            try:
                client_method = getattr(self.client, method_name)
                async for item in client_method(*args, **kwargs):
                    logger.info("Yielding item from client")
                    yield item
                break  # Successfully completed, exit the loop
            except asyncio.CancelledError:
                logger.warning("Operation cancelled, cleaning up")
                raise
            except Exception as e:
                logger.error(f"Error while making request: {str(e)}")
                raise
