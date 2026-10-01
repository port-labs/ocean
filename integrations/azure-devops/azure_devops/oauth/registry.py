from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import ProviderDefaults

# Azure DevOps' resource id in Entra ID, the same for every tenant.
ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider, if configured."""
    settings = ocean.config.identity_propagation.oauth.azure_devops
    if settings is None:
        return

    ocean.register_oauth_provider(
        defaults=ProviderDefaults(
            authorize_url="https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            # offline_access is what makes Entra ID issue a refresh token; without it
            # an Azure DevOps user re-authenticates roughly hourly.
            scopes=f"{ADO_RESOURCE_ID}/user_impersonation offline_access",
        ),
        settings=settings,
    )
