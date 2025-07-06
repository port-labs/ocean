from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aiobotocore.session import AioSession
from loguru import logger
from typing import Any, AsyncIterator
from aws.auth.utils import AWSSessionError


class SingleAccountHealthCheckMixin(AWSSessionStrategy, HealthCheckMixin):

    async def healthcheck(self) -> bool:
        try:
            session = await self.provider.get_session()
            async with session.create_client("sts", region_name=None) as sts:
                identity = await sts.get_caller_identity()
                logger.info(f"Validated single account: {identity['Account']}")
            return True
        except Exception as e:
            logger.error(f"Single account health check failed: {e}")
            raise AWSSessionError("Single account is not accessible") from e


class SingleAccountStrategy(SingleAccountHealthCheckMixin):
    """Strategy for handling a single AWS account."""

    async def create_session(self, **kwargs: Any) -> AioSession:
        return await self.provider.get_session(**kwargs)

    async def create_session_for_each_account(
        self, **kwargs: Any
    ) -> AsyncIterator[AioSession]:
        session = await self.create_session(**kwargs)
        yield session
