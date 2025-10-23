from abc import ABC, abstractmethod

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.clients.base import AbstractAzureClient
from pydantic import BaseModel


class BaseExporter(ABC):
    def __init__(
        self,
        client: AbstractAzureClient,
    ):
        self.client = client

    @abstractmethod
    def get_paginated_resources(
        self, options: BaseModel
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
