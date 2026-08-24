from port_ocean.context.ocean import ocean
from port_ocean.identity_propagation.oauth_broker.providers import ProviderDefaults


def register_oauth_provider() -> None:
    """Register this integration's identity-propagation OAuth provider, if configured."""
    settings = ocean.config.identity_propagation.oauth.github
    if settings is None:
        return

    ocean.register_oauth_provider(
        defaults=ProviderDefaults(
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            # GitHub App user-to-server tokens: access is controlled by the App
            # Manifest permissions, not by OAuth scopes. Default is empty; set
            # OAUTH_GITHUB_SCOPE only if using a classic OAuth App instead.
            scopes="",
        ),
        settings=settings,
    )
