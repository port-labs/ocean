"""
Bearer token authentication handler.
"""

from custom.auth.base import AuthHandler


class BearerTokenAuth(AuthHandler):
    """Bearer token authentication"""

    def setup(self) -> None:
        token = self.config.get("api_token")
        if token:
            self.client.headers["Authorization"] = f"Bearer {token}"
