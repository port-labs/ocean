from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aws.auth.utils import (
    normalize_arn_list,
    AWSSessionError,
    CredentialsProviderError,
)
from aiobotocore.session import AioSession
from loguru import logger
import asyncio
from typing import Any, AsyncIterator, Dict, List, Callable, Awaitable
from aws.auth.utils import extract_account_from_arn


class MultiAccountHealthCheckMixin(HealthCheckMixin):
    def __init__(
        self,
        config: Dict[str, Any],
        session_creator: Callable[
            [str, str], Awaitable[AioSession]
        ],  # (arn, session_name) -> AioSession
    ):
        self.config = config
        self._create_session = session_creator
        self._valid_arns: List[str] = []

    @property
    def valid_arns(self) -> List[str]:
        return self._valid_arns

    async def healthcheck(self) -> bool:
        account_role_arns = self.config.get("account_role_arn")
        arns = normalize_arn_list(account_role_arns)
        if not arns:
            logger.error("No account_role_arn(s) provided for healthcheck.")
            return False

        batch_size = 10
        for i in range(0, len(arns), batch_size):
            batch = arns[i : i + batch_size]
            tasks = [self._can_assume_role(arn) for arn in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for arn, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Health check failed for ARN {arn}: {result}")
                    continue
                if result:
                    logger.info(f"Health check passed for ARN {arn}")
                    self._valid_arns.append(arn)
                else:
                    logger.warning(f"Health check failed for ARN {arn}")

        if not self._valid_arns:
            logger.error("Health check failed for all ARNs.")
            raise AWSSessionError("No accounts are accessible after health check.")

        return True

    async def _can_assume_role(self, arn: str) -> bool:
        try:
            await self._create_session(arn, "HealthCheckSession")
            return True
        except CredentialsProviderError as e:
            logger.error(f"Credentials error for ARN {arn}: {e}")
            return False
        except Exception as e:
            logger.error(f"General error for ARN {arn}: {e}")
            return False


class MultiAccountStrategy(AWSSessionStrategy, MultiAccountHealthCheckMixin):
    """Strategy for handling multiple AWS accounts using explicit role ARNs."""

    async def create_session(self, **kwargs: Any) -> AioSession:
        try:

            arn = kwargs["arn"]
            session_kwargs = {
                "region": kwargs.get(
                    "region"
                ),  # if region is not provided, an account session is created
                "role_arn": arn,
                "role_session_name": kwargs.get("session_name", "OceanRoleSession"),
            }
            if self.config.get("external_id"):
                session_kwargs["external_id"] = self.config["external_id"]

            session = await self.provider.get_session(**session_kwargs)
            return session

        except CredentialsProviderError as e:
            logger.error(f"Credentials error for ARN {arn}: {e}")
            raise AWSSessionError(f"Credentials error for ARN {arn}: {e}") from e

        except Exception as e:
            logger.error(f"Session error for ARN {arn}: {e}")
            raise AWSSessionError(f"Session error for ARN {arn}: {e}") from e

    async def create_session_for_each_account(
        self, **kwargs: Any
    ) -> AsyncIterator[AioSession]:
        for arn in self.valid_arns:
            session = await self.create_session(arn=arn, **kwargs)
            setattr(
                session, "_AccountId", extract_account_from_arn(arn)
            )  # hack to faciliate logging
            yield session
