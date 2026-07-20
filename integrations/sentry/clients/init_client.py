from clients.sentry import SentryClient
from port_ocean.context.ocean import ocean


def init_client() -> SentryClient:
    sentry_client = SentryClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
    return sentry_client
