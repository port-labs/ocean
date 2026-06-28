from aiobotocore.session import AioSession
from typing import List, Set, Optional
from loguru import logger

from aws import Consts
from aws.utils import LocationUtils
from integration import AWSResourceSelector
from port_ocean.context.ocean import ocean


class RegionResolver:
    """Handles AWS region discovery and filtering."""

    def __init__(
        self,
        session: AioSession,
        selector: AWSResourceSelector,
        account_id: Optional[str] = None,
    ):
        self.session = session
        self.selector = selector
        self.account_id = account_id

    async def get_enabled_regions(self) -> List[str]:
        if LocationUtils.get_partition() != Consts.default_partition:
            return await LocationUtils.get_all_available_regions(self.session)

        async with self.session.create_client("account", region_name=None) as client:
            response = await client.list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )
            regions = [region["RegionName"] for region in response.get("Regions", [])]
            logger.debug(f"Retrieved enabled regions: {regions}")
            return regions

    async def get_allowed_regions(self) -> Set[str]:
        enabled_regions = await self.get_enabled_regions()
        allowed_regions = {
            region
            for region in enabled_regions
            if self.selector.is_region_allowed(region)
        }
        return allowed_regions
