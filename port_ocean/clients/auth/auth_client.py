from abc import ABC, abstractmethod

import httpx


class AuthClient(ABC):

    @abstractmethod
    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        pass
