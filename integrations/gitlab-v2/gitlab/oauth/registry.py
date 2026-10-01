from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import ProviderDefaults


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider, if configured."""
    settings = ocean.config.identity_propagation.oauth.gitlab
    if settings is None:
        return

    ocean.register_oauth_provider(
        defaults=ProviderDefaults(
            authorize_url="{host}/oauth/authorize",
            token_url="{host}/oauth/token",
            scopes="api",
            default_host="https://gitlab.com",
        ),
        settings=settings,
    )
