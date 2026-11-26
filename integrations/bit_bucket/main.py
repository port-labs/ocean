import asyncio
import logging
from .integration import BitbucketOceanIntegration
from .config import CONFIG

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

async def main():
    """Main async function to run the Bitbucket integration."""
    try:
        integration = BitbucketOceanIntegration(CONFIG)
        await integration.ingest_data_to_port()
    except Exception as e:
        logging.error(f"Unexpected error during execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())