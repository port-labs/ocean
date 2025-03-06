from port_ocean.context.ocean import ocean
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.webhook.webhook_client import BitbucketWebhookClient


def init_client() -> BitbucketClient:
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        username=ocean.integration_config.get("bitbucket_username"),
        app_password=ocean.integration_config.get("bitbucket_app_password"),
        workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
    )
    return client


def init_webhook_client() -> BitbucketWebhookClient:
    return BitbucketWebhookClient(
        secret=ocean.integration_config.get("bitbucket_webhook_secret", None),
        workspace=ocean.integration_config["bitbucket_workspace"],
        username=ocean.integration_config.get("bitbucket_username"),
        app_password=ocean.integration_config.get("bitbucket_app_password"),
        workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
    )
