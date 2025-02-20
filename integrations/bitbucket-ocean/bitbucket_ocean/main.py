import asyncio
import logging
from .integration import BitbucketOceanIntegration
from .config import CONFIG

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    integration = BitbucketOceanIntegration(CONFIG)
    asyncio.run(integration.ingest_data_to_port())
