"""
Simple authentication handlers.

Provides basic authentication strategies: bearer token, API key, basic auth, and no auth.
"""

import httpx

from http_server.auth.base import AuthHandler


class BearerTokenAuth(AuthHandler):
    """Bearer token authentication"""

    def setup(self) -> None:
        token = self.config.get("api_token")
        if token:
            self.client.headers["Authorization"] = f"Bearer {token}"


class ApiKeyAuth(AuthHandler):
    """API key authentication"""

    def setup(self) -> None:
        api_key = self.config.get("api_key")
        key_header = self.config.get("api_key_header", "X-API-Key")
        if api_key and key_header:
            self.client.headers[key_header] = api_key


class BasicAuth(AuthHandler):
    """Basic authentication"""

    def setup(self) -> None:
        username = self.config.get("username")
        password = self.config.get("password")
        if username and password:
            self.client.auth = httpx.BasicAuth(username, password)


class NoAuth(AuthHandler):
    """No authentication"""

    def setup(self) -> None:
        pass
