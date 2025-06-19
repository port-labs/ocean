from typing import AsyncIterator, Tuple
from aiobotocore.session import AioSession
from loguru import logger
from auth.strategy._abstract import AbstractStrategy, RegionResolver


class MultiAccountStrategy(AbstractStrategy):

    async def sanity_check(self) -> bool:
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[Tuple[str, AioSession]]:
        pass

    async def _get_accessible_credentials(
        self,
    ) -> AsyncIterator[Tuple[str, AioSession]]:
        role_arns = self.provider.config["account_read_role_arns"]
        if not role_arns:
            logger.warning("No accounts specified in config; returning empty iterator.")
            return
        for role_arn in role_arns:
            account_session = await self.provider.get_session(role_arn=role_arn)
            has_permission = await self.check_permission(role_arn, account_session)
            if not has_permission:
                logger.warning(
                    f"Skipping inaccessible account due to insufficient permissions: {role_arn}"
                )
                continue
            yield role_arn, account_session

    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]:
        async for role_arn, account_session in self.get_accessible_accounts():
            resolver = RegionResolver(account_session, self.selector)
            allowed_regions = await resolver.get_allowed_regions()
            for region in allowed_regions:
                yield await self.provider.get_session(role_arn=role_arn, region=region)
