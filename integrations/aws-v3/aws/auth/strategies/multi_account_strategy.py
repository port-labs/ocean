from aws.auth.strategies.base import AWSSessionStrategy, HealthCheckMixin
from aws.auth.types import AccountInfo
from aws.auth.utils import (
    normalize_arn_list,
    AWSSessionError,
    extract_account_from_arn,
)
from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from loguru import logger
import asyncio
from typing import Any, AsyncIterator


class MultiAccountHealthCheckMixin(AWSSessionStrategy, HealthCheckMixin):
    """Mixin for multi-account health checking with batching and concurrency."""

    DEFAULT_CONCURRENCY = 10
    DEFAULT_BATCH_SIZE = 10

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

        self._valid_arns: list[str] = []
        self._valid_sessions: dict[str, AioSession] = {}

    @property
    def valid_arns(self) -> list[str]:
        """Get the list of valid ARNs that passed health check."""
        return getattr(self, "_valid_arns", [])

    async def _can_assume_role(self, arn: str) -> AioSession | None:
        """Check if role can be assumed and return the session if successful."""
        try:
            session_kwargs = {
                "role_arn": arn,
                "role_session_name": "OceanRoleSession",
                "region": self.config.get("region"),
            }
            if self.config.get("external_id"):
                session_kwargs["external_id"] = self.config["external_id"]

            session = await self.provider.get_session(**session_kwargs)
            return session
        except Exception as e:
            logger.warning(f"Health check failed for role ARN {arn}: {e}")
            return None

    async def healthcheck(self) -> bool:
        arns = normalize_arn_list(self.config.get("account_role_arn", []))
        if not arns:
            logger.error("No account_role_arn(s) provided for healthcheck")
            return False

        logger.info(f"Starting AWS account health check for {len(arns)} role ARNs")

        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async def check_arn(arn: str) -> tuple[str, AioSession | None]:
            async with semaphore:
                session = await self._can_assume_role(arn)
                return arn, session

        total_batches = (
            len(arns) + self.DEFAULT_BATCH_SIZE - 1
        ) // self.DEFAULT_BATCH_SIZE
        for batch_num, batch_start in enumerate(
            range(0, len(arns), self.DEFAULT_BATCH_SIZE), 1
        ):
            batch = arns[batch_start : batch_start + self.DEFAULT_BATCH_SIZE]
            logger.debug(
                f"Processing batch {batch_num}/{total_batches} ({len(batch)} role ARNs)"
            )

            tasks = [check_arn(arn) for arn in batch]

            successful = 0
            for arn, task in zip(batch, tasks):
                try:
                    arn, session = await task
                    if session:
                        self._valid_arns.append(arn)
                        self._valid_sessions[arn] = session
                        successful += 1
                        account_id = extract_account_from_arn(arn)
                        logger.debug(f"Role ARN validated for account {account_id}")
                except Exception as e:
                    logger.warning(f"Health check failed for role ARN {arn}: {e}")

            logger.info(
                f"Batch {batch_num}/{total_batches}: {successful}/{len(batch)} role ARNs validated"
            )

        logger.info(
            f"Health check complete: {len(self._valid_arns or [])}/{len(arns)} role ARNs validated successfully"
        )

        if not self._valid_arns:
            raise AWSSessionError("No accounts are accessible after health check")

        return True


class MultiAccountStrategy(MultiAccountHealthCheckMixin):
    """Strategy for handling multiple AWS accounts using explicit role ARNs."""

    async def get_account_sessions(
        self, **kwargs: Any
    ) -> AsyncIterator[tuple[AccountInfo, AioSession]]:
        if not (self._valid_arns and self._valid_sessions):
            await self.healthcheck()
        if not (self._valid_arns and self._valid_sessions):
            raise AWSSessionError(
                "Account sessions not initialized. Run healthcheck first."
            )

        logger.info(f"Providing {len(self._valid_arns)} pre-validated AWS sessions")

        for arn in self._valid_arns:
            session = self._valid_sessions[arn]
            account_id = extract_account_from_arn(arn)
            account_info: AccountInfo = {
                "Id": account_id,
                "Arn": f"arn:aws:iam::{account_id}:root",
            }
            yield account_info, session

        logger.debug(
            f"Session provision complete: {len(self._valid_arns)} sessions yielded"
        )
