from port_ocean.context.ocean import ocean
from okta.client import OktaClient


def create_okta_client() -> OktaClient:
    """Create and configure Okta client with credentials from integration config"""
    domain = ocean.integration_config.get("okta_domain")
    api_token = ocean.integration_config.get("okta_api_token")
    
    return OktaClient(
        domain=domain,
        api_token=api_token,
    )