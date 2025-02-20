import base64
import logging
from port_ocean.clients.auth.auth_client import AuthClient

class CustomAuthClient(AuthClient):
    def refresh_request_auth_creds(self):
        """Basic Authentication does not require refreshing."""
        logging.debug("Basic Authentication does not require refreshing credentials.")

def get_auth_token(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode()).decode()
