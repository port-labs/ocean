from ocean_stub import OceanIntegration
from resources.base import BaseFetcher
from utils.logger import logger

class SpaceliftOceanIntegration(OceanIntegration):
    async def fetch_all(self):
        fetcher_classes = BaseFetcher.get_all_fetchers()

        logger.info(f"Found {len(fetcher_classes)} registered fetchers.")
        for fetcher_cls in fetcher_classes:
            fetcher = fetcher_cls()
            logger.info(f"Running fetcher for kind: {fetcher.kind}")
            async for entity in fetcher.fetch():
                logger.debug(f"Yielded entity: {entity['identifier']}")
                yield entity

app = SpaceliftOceanIntegration()
