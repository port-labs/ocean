from typing import cast

from port_ocean.context.ocean import ocean

from client import BitbucketClient


def initialize_client() -> BitbucketClient:
    return BitbucketClient(
        username=ocean.integration_config["bitbucket_username"],
        password=ocean.integration_config["bitbucket_password"],
        base_url=ocean.integration_config["bitbucket_base_url"],
        webhook_secret=ocean.integration_config["bitbucket_webhook_secret"],
        app_host=ocean.app.base_url,
        is_version_8_7_or_older=cast(
            bool,
            ocean.integration_config.get("bitbucket_is_version_8_point_7_or_older"),
        ),
    )
