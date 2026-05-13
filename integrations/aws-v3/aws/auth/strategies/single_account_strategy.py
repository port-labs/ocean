import os
from typing import Any, AsyncIterator

from aiobotocore.session import AioSession
from loguru import logger

from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
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
            # =========================
            # MOCK MODE (NO AWS AT ALL)
            # =========================
            if os.getenv("AWS_MOCK_MODE") == "true":
                self.account_id = "123456789012"

                # create a REAL session object (even if unused)
                self._session = await self.provider.get_session(
                    aws_access_key_id="mock",
                    aws_secret_access_key="mock",
                    aws_session_token="mock"
                )

                logger.warning("AWS MOCK MODE ENABLED - using fake AWS session")
                return True

            # =========================
            # REAL AWS MODE
            # =========================
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

            async with session.create_client("sts", region_name="us-east-1") as sts:
                identity = await sts.get_caller_identity()

            self.account_id = identity["Account"]
            self._session = session

            logger.info(f"Validated single account: {self.account_id}")
            return True

        except Exception as e:
            logger.error(f"Single account health check failed: {e}")

            if os.getenv("AWS_MOCK_MODE", "false").lower() == "true":
                logger.warning("AWS MOCK MODE: continuing despite healthcheck failure")

                self.account_id = "123456789012"
                self._session = None
                return True

            raise AWSSessionError("Single account is not accessible") from e


class SingleAccountStrategy(SingleAccountHealthCheckMixin):

    async def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:

        if not self.account_id:
            await self.healthcheck()

        if not self.account_id:
            raise AWSSessionError("Account ID is not set for single account session.")

        account_info = {
            "Id": self.account_id,
            "Name": f"Account {self.account_id}",
        }

        # IMPORTANT: allow mock session safely
        yield account_info, self._session