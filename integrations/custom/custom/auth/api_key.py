"""
API key authentication handler.
"""

from custom.auth.base import AuthHandler


class ApiKeyAuth(AuthHandler):
    """API key authentication"""

    def setup(self) -> None:
        api_key = self.config.get("api_key")
        if api_key:
            key_header = self.config.get("api_key_header", "X-API-Key")
            self.client.headers[key_header] = api_key
