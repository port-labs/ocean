from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aiobotocore.session import AioSession
from loguru import logger
from typing import Any, AsyncIterator
from aws.auth.utils import AWSSessionError
from aws.auth.providers.base import CredentialProvider


class SingleAccountHealthCheckMixin(AWSSessionStrategy, HealthCheckMixin):
    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

        self._session: AioSession | None = None
        self.account_id: str | None = None

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
            self._session = session
            return True
        except Exception as e:
            logger.error(f"Single account health check failed: {e}")
            raise AWSSessionError("Single account is not accessible") from e


class SingleAccountStrategy(SingleAccountHealthCheckMixin):
    """Strategy for handling a single AWS account."""

    async def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        if not self._session:
            await self.healthcheck()
        if not self._session:
            raise AWSSessionError(
                "Session could not be established for single account."
            )
        account_id = self.account_id
        if account_id is None:
            raise AWSSessionError("Account ID is not set for single account session.")
        account_info = {
            "Id": account_id,
            "Name": f"Account {account_id}",
        }
        yield account_info, self._session
