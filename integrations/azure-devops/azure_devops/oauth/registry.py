from pydantic import BaseModel

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# Azure DevOps' resource ID in Entra ID, the same for every tenant.
_ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"

# offline_access makes Entra ID issue a refresh token; without it the user
# re-authenticates roughly every hour.
_SCOPES = f"{_ADO_RESOURCE_ID}/user_impersonation offline_access"


class OAuthConfig(BaseModel):
    """Identity-propagation OAuth credentials for Azure DevOps.

    Set via ``OCEAN__INTEGRATION__CONFIG__IDENTITY_OAUTH__*`` env vars.
    """

    tenant_id: str
    client_id: str
    client_secret: str


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider.

    No-op when the ``identity_oauth`` config block is absent.
    """
    raw = ocean.integration_config.get("identity_oauth")
    if not raw:
        return

    cfg = OAuthConfig(**raw)
    tenant = cfg.tenant_id

    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
            token_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            scopes=_SCOPES,
        )
    )
