"""Abstract exporter for Okta resources."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from okta.clients.http.client import OktaClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


TClient = TypeVar("TClient", bound=OktaClient)


class AbstractOktaExporter(Generic[TClient], ABC):
    """Abstract base class for Okta resource exporters."""

    def __init__(self, client: TClient) -> None:
        """Initialize the exporter with an Okta client.

        Args:
            client: The Okta client instance
        """
        self.client = client

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM: ...

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
