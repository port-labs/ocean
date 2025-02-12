from abc import ABC, abstractmethod

import httpx

from port_ocean.helpers.retry import register_on_retry_callback


class RetryRequestClient(ABC):
    def __init__(self) -> None:
        register_on_retry_callback(self.refresh_request)

    @abstractmethod
    def refresh_request(self, request: httpx.Request) -> httpx.Request:
        pass
