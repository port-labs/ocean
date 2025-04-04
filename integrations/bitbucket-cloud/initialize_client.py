from port_ocean.context.ocean import ocean
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.base_client import BitbucketBaseClient
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
from bitbucket_cloud.helpers.utils import BitbucketRateLimiterConfig
from bitbucket_cloud.helpers.multiple_token import BitbucketClientManager


def init_client() -> BitbucketClient:
    return BitbucketClient.create_from_ocean_config()


def init_webhook_client() -> BitbucketWebhookClient:
    return BitbucketWebhookClient(
        secret=ocean.integration_config["webhook_secret"],
        base_client=BitbucketBaseClient.create_from_ocean_config()
    )


def init_multiple_client() -> BitbucketClientManager:
    return BitbucketClientManager(
        workspace=ocean.integration_config["bitbucket_workspace"],
        host=ocean.integration_config["bitbucket_host_url"],
        limit_per_client=BitbucketRateLimiterConfig.LIMIT,
        window=BitbucketRateLimiterConfig.WINDOW,
    )
