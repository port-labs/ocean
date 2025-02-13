from abc import ABC, abstractmethod

import httpx

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import register_on_retry_callback


class OAuthClient(ABC):
    def __init__(self) -> None:
        """
        A client that can refresh a request using an access token.
        """
        if self.is_oauth_enabled():
            register_on_retry_callback(self.refresh_request_oauth_creds)

    @abstractmethod
    def is_oauth_enabled(self) -> bool:
        pass

    @abstractmethod
    def refresh_request_oauth_creds(self, request: httpx.Request) -> httpx.Request:
        pass

    @property
    def external_access_token(self) -> str | None:
        return ocean.app.load_external_oauth_access_token()

    @property
    @abstractmethod
    def access_token(self) -> str:
        pass
