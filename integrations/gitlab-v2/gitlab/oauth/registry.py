from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import OAuth2Provider

# `api` lets the token call the GitLab API as the authorizing user.
# GitLab issues a refresh token on the authorization-code grant without an extra scope.
_SCOPES = "api"
_DEFAULT_HOST = "https://gitlab.com"


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

    host = str(ocean.integration_config.get("gitlab_host") or _DEFAULT_HOST).rstrip("/")

    ocean.register_oauth_provider(
        OAuth2Provider(
            target=ocean.config.integration.type,
            authorize_url=f"{host}/oauth/authorize",
            token_url=f"{host}/oauth/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )
    )
