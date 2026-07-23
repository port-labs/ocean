from abc import ABC, abstractmethod

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.cursor_agents_client import CursorAgentsClient


class AbstractCursorExporter(ABC):
    """Abstract base class for Cursor Cloud Agents resource exporters."""

    def __init__(self, client: CursorAgentsClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(
        self, *, include_archived: bool = False
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError
