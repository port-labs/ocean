from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
import httpx
from loguru import logger

@ocean.on_resync("apiItem")
async def sync_api_items(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    api_url = ocean.integration_config["api_url"]
    auth_token = ocean.integration_config.get("auth_token")

    headers = {"Accept": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

    logger.info(f"Fetched {len(data)} records from API")

    yield data
