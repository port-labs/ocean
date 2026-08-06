import base64
import logging
from port_ocean.clients.auth.auth_client import AuthClient

logger = logging.getLogger(__name__)

class CustomAuthClient(AuthClient):
    async def refresh_request_auth_creds(self):
        """Basic Authentication does not require credential refresh."""
        logger.debug("Basic Authentication does not require refreshing credentials.")

class BasicAuth:
    """Encapsulates basic authentication logic for Bitbucket API."""
    
    @staticmethod
    def get_auth_token(username: str, password: str) -> str:
        """Generates a base64-encoded authentication token for HTTP Basic Authentication."""
        if not username or not password:
            logger.warning("Username or password is missing while generating auth token.")
            raise ValueError("Username and password must be provided.")
        
        auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()
        logger.debug("Generated authentication token successfully.")
        return auth_token