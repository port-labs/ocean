from port_ocean.context.ocean import ocean

from .client import BitbucketClient


def initialize_client() -> BitbucketClient:
    return BitbucketClient(
        username=ocean.integration_config["username"],
        password=ocean.integration_config["password"],
        base_url=ocean.integration_config["base_url"],
        webhook_secret=ocean.integration_config["webhook_secret"],
        app_host=ocean.app.base_url,
    )
