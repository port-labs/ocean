from port_ocean.context.ocean import ocean
from azure_integration.clients.client import SDKClient
from azure_integration.helpers.rate_limiter import TokenBucketRateLimiter
from azure_integration.helpers.subscription import SubscriptionManager
from azure_integration.models import AuthCredentials


def init_client_and_sub_manager() -> tuple[SDKClient, SubscriptionManager]:
    batch_size = ocean.integration_config["subscription_batch_size"]
    credentials = AuthCredentials(
        tenant_id=ocean.integration_config["azure_tenant_id"],
        client_id=ocean.integration_config["azure_client_id"],
        client_secret=ocean.integration_config["azure_client_secret"],
    )
    rate_limitter = TokenBucketRateLimiter(capacity=250, refill_rate=25)
    client = SDKClient(credentials, rate_limitter)
    sub_manager = SubscriptionManager(credentials, rate_limitter, int(batch_size))
    return client, sub_manager
