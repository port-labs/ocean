from port_ocean.clients.auth.auth_client import AuthClient
from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import (
    RetryConfig,
    register_on_retry_callback,
    register_retry_config_callback,
)
from loguru import logger

OAUTH_RETRYABLE_METHODS = frozenset(
    ["HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS", "TRACE"]
)


def _oauth_retry_config() -> RetryConfig:
    """Retry POST on OAuth integrations so 401 can refresh tokens before retry."""
    return RetryConfig(retryable_methods=OAUTH_RETRYABLE_METHODS)


class OAuthClient(AuthClient):
    def __init__(self) -> None:
        """
        A client that can refresh a request using an access token.
        """
        if self.is_oauth_enabled():
            register_on_retry_callback(self.refresh_request_auth_creds)
            register_retry_config_callback(_oauth_retry_config)
            logger.info(
                "OAuth retry callback registered for auth credential refresh",
                client_class=self.__class__.__name__,
            )

    def is_oauth_enabled(self) -> bool:
        return ocean.app.config.oauth_access_token_file_path is not None

    @property
    def external_access_token(self) -> str:
        access_token = ocean.app.load_external_oauth_access_token()
        if access_token is None:
            raise ValueError("No external access token found")
        logger.debug("Loaded external OAuth access token for request authentication")
        return access_token
