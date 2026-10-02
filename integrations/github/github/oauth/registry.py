from loguru import logger
from pydantic import BaseModel

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# `repo` covers issues and pull requests on private repositories.
# Classic GitHub OAuth apps do not return a refresh token; the token is used until rejected.
_SCOPES = "repo"
_GITHUB_API_HOST = "https://api.github.com"
_GITHUB_WEB_HOST = "https://github.com"


class OAuthConfig(BaseModel):
    """Identity-propagation OAuth credentials for GitHub.

    Set via ``OCEAN__INTEGRATION__CONFIG__IDENTITY_OAUTH__*`` env vars.
    """

    client_id: str
    client_secret: str


def oauth_web_host(api_host: str) -> str:
    """Map the configured API host to the host that serves `/login/oauth`."""
    host = api_host.rstrip("/")
    if host == _GITHUB_API_HOST:
        return _GITHUB_WEB_HOST
    suffix = "/api/v3"
    if host.endswith(suffix):
        return host[: -len(suffix)]
    return host


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
    web_host = oauth_web_host(
        str(ocean.integration_config.get("github_host") or _GITHUB_API_HOST)
    )
    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"{web_host}/login/oauth/authorize",
            token_url=f"{web_host}/login/oauth/access_token",
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            scopes=_SCOPES,
        )
    )
