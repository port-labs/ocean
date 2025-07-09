from aws.auth.strategies.base import (
    AWSSessionStrategy,
    HealthCheckMixin,
    AccountContext,
    AccountDetails,
)
from aiobotocore.session import AioSession
from loguru import logger
from typing import Any, AsyncIterator, TYPE_CHECKING
from aws.auth._helpers.exceptions import AWSSessionError
from aws.auth.providers.base import CredentialProvider

if TYPE_CHECKING:
    from mypy_boto3_sts.type_defs import GetCallerIdentityResponseTypeDef


class SingleAccountHealthCheckMixin(HealthCheckMixin):
    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

        self._session: AioSession | None = None
        self._identity: dict[str, Any] | None = None

    async def healthcheck(self) -> bool:
        try:
            session_kwargs = {
                "aws_access_key_id": self.config["aws_access_key_id"],
                "aws_secret_access_key": self.config["aws_secret_access_key"],
                "aws_session_token": self.config.get("aws_session_token"),
            }
            session = await self.provider.get_session(**session_kwargs)
            async with session.create_client("sts", region_name=None) as sts:
                identity: GetCallerIdentityResponseTypeDef = (
                    await sts.get_caller_identity()
                )
                self._identity = dict(identity)
                logger.info(f"Validated single account: {self._identity['Account']}")
            self._session = session
            return True
        except Exception as e:
            logger.error(f"Single account health check failed: {e}")
            raise AWSSessionError("Single account is not accessible") from e


class SingleAccountStrategy(SingleAccountHealthCheckMixin, AWSSessionStrategy):
    """Strategy for handling a single AWS account."""

    async def get_account_sessions(
        self,
    ) -> AsyncIterator[AccountContext]:
        if not self._session:
            await self.healthcheck()
        if not self._session:
            raise AWSSessionError(
                "Session could not be established for single account."
            )
        if not self._identity:
            raise AWSSessionError(
                "Identity could not be established for single account."
            )
        account_id = self._identity["Account"]
        account_info = AccountDetails(
            Id=account_id,
            Name=f"Account {account_id}",
            Arn="",  # Excluded because ARN from get_caller_identity is only a reflection of the user/role making the request and not the arn of the account
        )
        yield AccountContext(details=account_info, session=self._session)
