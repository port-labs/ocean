import base64

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

    async def get_client(self, client_type: str) -> AbstractGithubClient:
        """Get or create a client instance from Ocean configuration.

        Args:
            client_type: Type of client to create ("rest" or other supported types)

        Returns:
            An instance of AbstractGithubClient

        Raises:
            ValueError: If client_type is invalid
        """
        token = ocean.integration_config.get("github_token")
        app_id = ocean.integration_config.get("app_id")
        app_private_key = ocean.integration_config.get("app_private_key")
        organization = ocean.integration_config["github_organization"]
        github_host = ocean.integration_config["github_host"]

        match client_type:
            case "rest":
                if app_id is not None and app_private_key is not None:
                    logger.info("app_id and private_key detected, using Github App")
                    if "rest_app" not in self._clients:
                        decoded_private_key = base64.b64decode(app_private_key)
                        rest_app = self._clients[
                            "rest_app"
                        ] = await GithubAppRestClient(
                            organization, github_host, app_id, decoded_private_key
                        ).set_up()
                        return rest_app
                    else:
                        return self._clients["rest_app"]
                elif token is not None:
                    logger.info(
                        "Github token found, using Rest Client with Token authentication"
                    )
                    if "rest_token" not in self._clients:
                        token_app = self._clients["rest_token"] = GithubRestClient(
                            token,
                            organization=organization,
                            github_host=organization,
                        )
                        return token_app
                    else:
                        return self._clients["rest_token"]
                raise ValueError(
                    "app_id and app_private_key must be passed in if github_token is not being used."
                )
            case _:
                raise ValueError("Unknown client type")


async def create_github_client(client_type: str = "rest") -> AbstractGithubClient:
    factory = GithubClientFactory()
    return await factory.get_client(client_type)
