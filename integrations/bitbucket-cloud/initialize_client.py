from port_ocean.context.ocean import ocean
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient


def init_client() -> BitbucketClient:
    return BitbucketClient.create_from_ocean_config()


def init_webhook_client() -> BitbucketWebhookClient:
    return BitbucketWebhookClient(
        secret=ocean.integration_config["webhook_secret"],
        workspace=ocean.integration_config["bitbucket_workspace"],
        host=ocean.integration_config["bitbucket_host_url"],
        username=ocean.integration_config.get("bitbucket_username"),
        app_password=ocean.integration_config.get("bitbucket_app_password"),
        workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
    )
