from gcp_core.gcp_client import GCPClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync()
async def resync_assets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    gcp_client = GCPClient.create_from_ocean_config()
    async for assets in gcp_client.generate_assets(kind):
        yield assets
