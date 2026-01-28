"""
API key authentication handler.
"""

from http_server.auth.base import AuthHandler


class ApiKeyAuth(AuthHandler):
    """API key authentication"""

    def setup(self) -> None:
        api_key = self.config.get("api_key")
        key_header = self.config.get("api_key_header", "X-API-Key")
        if api_key and key_header:
            self.client.headers[key_header] = api_key
