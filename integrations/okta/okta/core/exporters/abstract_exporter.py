"""Abstract exporter for Okta resources."""

from abc import ABC, abstractmethod
from typing import Any

from okta.clients.http.client import OktaClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class AbstractOktaExporter[T: OktaClient](ABC):
    """Abstract base class for Okta resource exporters."""

    def __init__(self, client: T) -> None:
        """Initialize the exporter with an Okta client.

        Args:
            client: The Okta client instance
        """
        self.client = client

    @abstractmethod
    async def get_resource[AnyOption: Any](self, options: AnyOption) -> RAW_ITEM: ...

    @abstractmethod
    def get_paginated_resources[
        AnyOption: Any
    ](self, options: AnyOption) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
