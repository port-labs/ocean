from port_ocean.clients.auth.auth_client import AuthClient
from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import register_on_retry_callback
from loguru import logger


class OAuthClient(AuthClient):
    def __init__(self) -> None:
        """
        A client that can refresh a request using an access token.
        """
        if self.is_oauth_enabled():
            register_on_retry_callback(self.refresh_request_auth_creds)
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
