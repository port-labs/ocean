from aws.auth.strategies.base import AWSSessionStrategy
from aiobotocore.session import AioSession
from loguru import logger
from typing import Any, AsyncIterator, Optional, Dict


class SingleAccountStrategy(AWSSessionStrategy):
    """Strategy for handling a single AWS account."""

    async def healthcheck(self) -> bool:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
        logger.info(f"Validated single account: {identity['Account']}")
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[Dict[str, Any]]:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            account_id: str = identity["Account"]
        logger.info(f"Accessing single account: {account_id}")
        yield {"Id": account_id, "Arn": identity["Arn"]}

    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            current_arn: str = identity["Arn"]
        if current_arn != arn:
            logger.warning(
                f"Requested ARN {arn} does not match current ARN {current_arn}"
            )
            return None
        return session
