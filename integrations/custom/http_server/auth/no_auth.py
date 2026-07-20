"""
No authentication handler.
"""

from http_server.auth.base import AuthHandler


class NoAuth(AuthHandler):
    """No authentication"""

    def setup(self) -> None:
        pass
