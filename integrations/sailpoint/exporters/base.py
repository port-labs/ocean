from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict

from ..client import SailPointClient


class BaseExporter(ABC):
    kind: str
    sp_path: str
    blueprint: str

    def __init__(self, client: SailPointClient, mapping, cfg):
        self.client = client
        self.mapping = mapping
        self.cfg = cfg

    def default_params(self) -> Dict[str, Any]:
        return {}

    async def fetch(self) -> AsyncIterator[Dict[str, Any]]:
        params = self.default_params()
        async for item in self.client.paginate(self.sp_path, params=params):
            yield item

    @abstractmethod
    async def ingest(self, ocean) -> None: ...
