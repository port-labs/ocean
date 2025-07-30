from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from port_ocean.core.ocean_types import RAW_ITEM

from base_client import BaseCheckmarxClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: BaseCheckmarxClient) -> None:
        self.client = client
