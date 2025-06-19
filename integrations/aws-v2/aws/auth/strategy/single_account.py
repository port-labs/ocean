from typing import AsyncIterator, Tuple

from aiobotocore.session import AioSession
from auth.strategy._abstract import RegionResolver, AbstractStrategy


class SingleAccountStrategy(AbstractStrategy):
    """
    A single account strategy is used when the user has a single account.
    It supports static credentials only.
    """

    async def sanity_check(self) -> bool:
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[Tuple[str, AioSession]]:
        pass

    async def _create_session_for_region(self, region: str) -> AioSession:
        return await self.provider.get_session(region=region)

    async def _get_allowed_regions(self, session: AioSession) -> set[str]:
        region_resolver = RegionResolver(session, self.selector)
        return await region_resolver.get_allowed_regions()

    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]:
        session = await self.provider.get_session()
        allowed_regions = await self._get_allowed_regions(session)
        for region in allowed_regions:
            yield await self._create_session_for_region(region)
