from loguru import logger
from pydantic import BaseModel

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# `api` lets the token call the GitLab API as the authorizing user.
# GitLab issues a refresh token on the authorization-code grant without an extra scope.
_SCOPES = "api"
_DEFAULT_HOST = "https://gitlab.com"


class OAuthConfig(BaseModel):
    """Identity-propagation OAuth credentials for GitLab.

    Set via ``OCEAN__INTEGRATION__CONFIG__IDENTITY_OAUTH__*`` env vars.
    The GitLab host comes from the existing ``gitlabHost`` config.
    """

    client_id: str
    client_secret: str


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider.

    No-op when the ``identity_oauth`` config block is absent.
    """
    raw = ocean.integration_config.get("identity_oauth")
    if not raw:
        if ocean.config.identity_propagation.enabled:
            logger.warning(
                "Identity propagation is enabled but identity_oauth is missing from the integration config"
            )
        return

    cfg = OAuthConfig(**raw)
    host = str(ocean.integration_config.get("gitlab_host") or _DEFAULT_HOST).rstrip(
        "/"
    )

    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"{host}/oauth/authorize",
            token_url=f"{host}/oauth/token",
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            scopes=_SCOPES,
        )
    )
