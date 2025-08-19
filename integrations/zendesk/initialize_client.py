from zendesk.client import ZendeskClient
from port_ocean.context.ocean import ocean


def create_zendesk_client() -> ZendeskClient:
    """Create ZendeskClient with current configuration."""
    config = ocean.integration_config
    
    return ZendeskClient(
        subdomain=config["zendesk_subdomain"],
        email=config.get("zendesk_email"),
        token=config.get("zendesk_token"),
        oauth_token=config.get("zendesk_oauth_token"),
    )