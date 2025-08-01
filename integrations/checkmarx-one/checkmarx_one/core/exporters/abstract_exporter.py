from abc import ABC

from base_client import BaseCheckmarxClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: BaseCheckmarxClient) -> None:
        self.client = client
