"""
Basic authentication handler.
"""

import httpx

from custom.auth.base import AuthHandler


class BasicAuth(AuthHandler):
    """Basic authentication"""

    def setup(self) -> None:
        username = self.config.get("username")
        password = self.config.get("password")
        if username and password:
            self.client.auth = httpx.BasicAuth(username, password)
