"""
No authentication handler.
"""

from custom.auth.base import AuthHandler


class NoAuth(AuthHandler):
    """No authentication"""

    def setup(self) -> None:
        pass
