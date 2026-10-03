from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# Azure DevOps' resource ID in Entra ID, the same for every tenant.
_ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"

# offline_access makes Entra ID issue a refresh token; without it the user
# re-authenticates roughly every hour.
_SCOPES = f"{_ADO_RESOURCE_ID}/user_impersonation offline_access"


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider.

    No-op when identity OAuth client credentials are absent.
    """
    tenant_id = ocean.integration_config.get("identity_oauth_tenant_id")
    client_id = ocean.integration_config.get("identity_oauth_client_id")
    client_secret = ocean.integration_config.get("identity_oauth_client_secret")

    if not tenant_id or not client_id or not client_secret:
        if ocean.config.identity_propagation.enabled:
            logger.warning(
                "Identity propagation is enabled but identityOauthTenantId/"
                "identityOauthClientId/identityOauthClientSecret are missing "
                "from the integration config"
            )
        return

    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
            token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )
    )
