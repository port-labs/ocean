from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aiobotocore.session import AioSession
from loguru import logger
from typing import Any, AsyncIterator
from aws.auth.utils import AWSSessionError


class SingleAccountHealthCheckMixin(AWSSessionStrategy, HealthCheckMixin):

    async def healthcheck(self) -> bool:
        try:
            access_key = self.config.get("aws_access_key_id")
            secret_key = self.config.get("aws_secret_access_key")
            token = self.config.get("aws_session_token")
            session_kwargs = {}
            if access_key and secret_key:
                session_kwargs = {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                    "aws_session_token": token,
                }
            session = await self.provider.get_session(**session_kwargs)
            async with session.create_client("sts", region_name=None) as sts:
                identity = await sts.get_caller_identity()
                self.account_id = identity["Account"]
                logger.info(f"Validated single account: {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"Single account health check failed: {e}")
            raise AWSSessionError("Single account is not accessible") from e


class SingleAccountStrategy(SingleAccountHealthCheckMixin):
    """Strategy for handling a single AWS account."""

    async def create_session(self, **kwargs: Any) -> AioSession:
        # Allow credentials to be passed via kwargs, or fallback to config/default
        access_key = kwargs.get("aws_access_key_id") or self.config.get(
            "aws_access_key_id"
        )
        secret_key = kwargs.get("aws_secret_access_key") or self.config.get(
            "aws_secret_access_key"
        )
        token = kwargs.get("aws_session_token") or self.config.get("aws_session_token")
        session_kwargs = {}
        if access_key and secret_key:
            session_kwargs = {
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
                "aws_session_token": token,
            }
        session = await self.provider.get_session(**session_kwargs)
        return session

    def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        async def _get_sessions() -> AsyncIterator[tuple[dict[str, str], AioSession]]:
            session = await self.create_session()
            account_id = getattr(self, "account_id", "unknown")
            account_info = {
                "Id": account_id,
                "Name": f"Account {account_id}",
            }
            yield account_info, session

        return _get_sessions()
