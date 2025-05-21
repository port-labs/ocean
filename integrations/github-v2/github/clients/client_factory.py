import base64
from typing import Any

from github.clients.app_client import GithubAppRestClient
from github.clients.rest_client import GithubRestClient
from github.clients.base_client import AbstractGithubClient
from port_ocean.context.ocean import ocean
from loguru import logger


class GithubClientFactory:
    _instance = None
    _clients: dict[str, AbstractGithubClient] = {}

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

    def app_configured(self) -> bool:
        return "app_id" in self.ocean_config and "app_private_key" in self.ocean_config

    async def get_client(self, client_type: str) -> AbstractGithubClient:
        """Get or create a client instance from Ocean configuration.

        Args:
            client_type: Type of client to create ("rest" or other supported types)

        Returns:
            An instance of AbstractGithubClient

        Raises:
            ValueError: If client_type is invalid
        """

        match client_type:
            case "rest":
                if self.app_configured():
                    logger.info("app_id and private_key detected, using Github App")
                    return await self._get_app_client()
                elif "token" in self.ocean_config:
                    logger.info(
                        "Github token found, using Rest Client with Token authentication"
                    )
                    return self._get_rest_client()

                raise ValueError(
                    "app_id and app_private_key must be passed if github_token is not being used."
                )
            case _:
                raise ValueError("Unknown client type")

    def _get_rest_client(self) -> AbstractGithubClient:
        if "rest_token" not in self._clients:
            token_app = self._clients["rest_token"] = GithubRestClient(
                self.ocean_config["token"],
                organization=self.ocean_config["organization"],
                github_host=self.ocean_config["github_host"],
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


async def create_github_client(client_type: str = "rest") -> AbstractGithubClient:
    factory = GithubClientFactory()
    return await factory.get_client(client_type)
