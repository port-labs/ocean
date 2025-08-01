import threading
from port_ocean.context.ocean import ocean
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
from typing import Optional

# Use None to indicate client hasn't been created yet
_client: Optional[BitbucketClient] = None
_client_lock = threading.Lock()


def init_client() -> BitbucketClient:
    """Initialize and return the BitbucketClient instance with lazy loading."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = BitbucketClient.create_from_ocean_config()
    return _client


def init_webhook_client() -> BitbucketWebhookClient:
    """Initialize and return the BitbucketWebhookClient instance."""
    return BitbucketWebhookClient(
        secret=ocean.integration_config["webhook_secret"],
        workspace=ocean.integration_config["bitbucket_workspace"],
        host=ocean.integration_config["bitbucket_host_url"],
        username=ocean.integration_config.get("bitbucket_username"),
        app_password=ocean.integration_config.get("bitbucket_app_password"),
        workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
    )
