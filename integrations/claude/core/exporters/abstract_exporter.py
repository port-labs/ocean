from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.claude_client import ClaudeClient


class AbstractClaudeExporter(ABC):
    """Abstract base class for Claude resource exporters."""

    def __init__(self, client: ClaudeClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass
