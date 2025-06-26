from .base import BaseFetcher
from integrations.spacelift.utils.logger import logger

class RegistryFetcher:
    def __init__(self):
        self.fetchers = BaseFetcher.get_all_fetchers()

    async def fetch_all(self):
        for fetcher_cls in self.fetchers:
            fetcher = fetcher_cls()
            logger.info(f"Resyncing resource kind: {fetcher.kind}")
            async for entity in fetcher.fetch():
                yield entity
