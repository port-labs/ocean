import base64
from typing import Optional

from .abstract_authenticator import (
    AbstractHarborAuthenticator,
    HarborToken,
    HarborHeaders,
)


class HarborBasicAuthenticator(AbstractHarborAuthenticator):
    """Harbor Basic Authentication using username:password"""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._token: Optional[HarborToken] = None

    async def get_token(self) -> HarborToken:
        """Get Harbor Basic Auth token (base64 encoded username:password)"""
        if not self._token:
            credentials = f"{self.username}:{self.password}"
            encoded_token = base64.b64encode(credentials.encode()).decode()

            self._token = HarborToken(
                token=encoded_token,
            )

        return self._token

    async def get_headers(self) -> HarborHeaders:
        """Get headers for Harbor API requests"""
        token = await self.get_token()

        return HarborHeaders(
            authorization=f"Basic {token.token}", accept="application/json"
        )
