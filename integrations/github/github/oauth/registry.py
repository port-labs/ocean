from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# `repo` covers issues and pull requests on private repositories.
# Classic GitHub OAuth apps do not return a refresh token; the token is used until rejected.
_SCOPES = "repo"
_GITHUB_API_HOST = "https://api.github.com"
_GITHUB_WEB_HOST = "https://github.com"


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

    No-op when identity OAuth client credentials are absent.
    """
    client_id = ocean.integration_config.get("identity_oauth_client_id")
    client_secret = ocean.integration_config.get("identity_oauth_client_secret")

    if not client_id or not client_secret:
        if ocean.config.identity_propagation.enabled:
            logger.warning(
                "Identity propagation is enabled but identityOauthClientId/"
                "identityOauthClientSecret are missing from the integration config"
            )
        return

    web_host = oauth_web_host(
        str(ocean.integration_config.get("github_host") or _GITHUB_API_HOST)
    )
    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"{web_host}/login/oauth/authorize",
            token_url=f"{web_host}/login/oauth/access_token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )
    )
