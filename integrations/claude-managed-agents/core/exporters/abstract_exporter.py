from abc import ABC, abstractmethod

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.anthropic_client import AnthropicClient


class AbstractAnthropicExporter(ABC):
    """Abstract base class for Claude Managed Agents resource exporters."""

    def __init__(self, client: AnthropicClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass
