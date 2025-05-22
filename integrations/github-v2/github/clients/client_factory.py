import base64
from typing import Any, Dict, Type
from github.clients.rest_client import GithubRestClient
from github.clients.graphql_client import GithubGraphQLClient
from github.clients.base_client import AbstractGithubClient
from port_ocean.context.ocean import ocean
from loguru import logger
from github.helpers.app import GithubApp
from github.helpers.utils import GithubClientType
from github.webhook.webhook_client import GithubWebhookClient


class GithubClientFactory:
    _instance = None
    _clients: Dict[GithubClientType, Type[AbstractGithubClient]] = {
        GithubClientType.REST: GithubRestClient,
        GithubClientType.GRAPHQL: GithubGraphQLClient,
        GithubClientType.WEBHOOK: GithubWebhookClient,
    }
    _instances: Dict[GithubClientType, AbstractGithubClient] = {}
    _gh_app: GithubApp | None = None
    _gh_app_token: str | None = None

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super(GithubClientFactory, cls).__new__(cls)
        return cls._instance

    @property
    def ocean_config(self) -> dict[str, Any]:
        app_id = ocean.integration_config.get("app_id")
        app_private_key = ocean.integration_config.get("app_private_key")
        token = ocean.integration_config.get("github_token")
        config = {
            "organization": ocean.integration_config["github_organization"],
            "github_host": ocean.integration_config["github_host"],
        }
        if app_id:
            config["app_id"] = app_id
        if app_private_key:
            config["app_private_key"] = app_private_key
        if token:
            config["token"] = token

        return config

    def gh_app_configured(self) -> bool:
        return "app_id" in self.ocean_config and "app_private_key" in self.ocean_config

    async def setup_gh_app(self) -> None:
        if self._gh_app is None:
            decoded_private_key = base64.b64decode(self.ocean_config["app_private_key"])
            self._gh_app = GithubApp(
                organization=self.ocean_config["organization"],
                github_host=self.ocean_config["github_host"],
                app_id=self.ocean_config["app_id"],
                private_key=decoded_private_key,
            )
        self._gh_app_token = await self._gh_app.get_token()

    async def get_client(
        self, client_type: GithubClientType, **kwargs: Any
    ) -> AbstractGithubClient:
        """Get or create a client instance from Ocean configuration.

        Args:
            client_type: Type of client to create ("rest" or other supported types)

        Returns:
            An instance of AbstractGithubClient

        Raises:
            ValueError: If client_type is invalid
        """

        if client_type not in self._clients:
            logger.error(f"Invalid client type: {client_type}")
            raise ValueError(f"Invalid client type: {client_type}")

        if client_type not in self._instances:
            if self.gh_app_configured():
                logger.info("Github app details found, setting up ...")
                await self.setup_gh_app()

            self._instances[client_type] = self._clients[client_type](
                token=self._gh_app_token or self.ocean_config["token"],
                organization=self.ocean_config["organization"],
                github_host=self.ocean_config["github_host"],
                gh_app=self._gh_app,
                **kwargs,
            )

            return token_app
        else:
            return self._clients["rest_token"]

    async def _get_app_client(self) -> AbstractGithubClient:
        if "rest_app" not in self._clients:
            decoded_private_key = base64.b64decode(self.ocean_config["app_private_key"])

            rest_app = self._clients["rest_app"] = await GithubAppRestClient(
                organization=self.ocean_config["organization"],
                github_host=self.ocean_config["github_host"],
                app_id=self.ocean_config["app_id"],
                private_key=decoded_private_key,
            ).set_up()

            return rest_app
        else:
            return self._clients["rest_app"]


async def create_github_client(
    client_type: GithubClientType | None = GithubClientType.REST, **kwargs: Any
) -> AbstractGithubClient:
    factory = GithubClientFactory()
    return await factory.get_client(client_type or GithubClientType.REST, **kwargs)
