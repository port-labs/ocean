from abc import ABC, abstractmethod

from integrations.spacelift.gpl_client import SpaceliftGraphQLClient
from integrations.spacelift.utils.logger import logger


class BaseFetcher(ABC):
    """
    Abstract base class for fetching Spacelift resources.
    Each subclass must define:
      - `kind`: the Port entity kind (e.g. "spacelift-space")
      - `fetch`: an async generator yielding Port entities
    """

    kind: str
    _registry = []

    def __init_subclass__(cls):
        if cls not in BaseFetcher._registry:
            BaseFetcher._registry.append(cls)

    @classmethod
    def get_all_fetchers(cls):
        return cls._registry

    def __init__(self):
        self.client = SpaceliftGraphQLClient()
        logger.debug(f"{self.__class__.__name__} initialized.")

    @abstractmethod
    async def fetch(self):
        """
        Subclasses must implement this to yield entity dicts like:
        {
            "identifier": str,
            "title": str,
            "properties": dict
        }
        """
        pass

    async def fetch_by_id(self, resource_id: str):
        """
        Optional override: used for real-time updates when webhook provides specific ID.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement fetch_by_id.")
