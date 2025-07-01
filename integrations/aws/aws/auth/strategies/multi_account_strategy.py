from aws.auth.strategies.base import AWSSessionStrategy
from aiobotocore.session import AioSession
from botocore.utils import ArnParser
from aws.auth.utils import (
    normalize_arn_list,
    extract_account_from_arn,
    AWSSessionError,
    CredentialsProviderError,
)
from loguru import logger
import asyncio
from typing import Any, AsyncIterator, Optional, Dict


class MultiAccountStrategy(AWSSessionStrategy):
    """Strategy for handling multiple AWS accounts using explicit role ARNs."""

    async def healthcheck(self) -> bool:
        account_role_arns = self.config.get("account_role_arn")
        arns = normalize_arn_list(account_role_arns)
        if not arns:
            logger.error("No organization_role_arn(s) provided for healthcheck.")
            return False
        tasks = [self._can_assume_role(arn) for arn in arns]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self._valid_arns = []
        for arn, result in zip(arns, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Health check failed for ARN {arn} due to exception: {result}"
                )
                continue
            if result:
                logger.info(f"Health check passed for ARN {arn}.")
                self._valid_arns.append(arn)
            else:
                logger.warning(f"Health check failed for ARN {arn}.")
        if not self._valid_arns:
            logger.error(
                "Health check failed for all ARNs. No accounts are accessible."
            )
            raise AWSSessionError(
                "Health check failed for all ARNs. No accounts are accessible."
            )
        return True

    async def _create_and_log_session(
        self, arn: str, session_name: str = "OceanRoleSession"
    ) -> AioSession:
        session_kwargs = {
            "region": None,
            "role_arn": arn,
            "role_session_name": session_name,
        }
        if self.config.get("external_id"):
            session_kwargs["external_id"] = self.config.get("external_id")
        session = await self.provider.get_session(**session_kwargs)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            logger.info(f"Successfully assumed role: {arn} as {identity['Arn']}")
        return session

    async def _can_assume_role(self, arn: str) -> bool:
        try:
            _ = await self._create_and_log_session(
                arn, session_name="HealthCheckSession"
            )
            return True
        except CredentialsProviderError as e:
            logger.error(
                f"Failed to assume role for ARN {arn} due to credentials error: {e}"
            )
            return False

    async def get_accessible_accounts(self) -> AsyncIterator[Dict[str, Any]]:
        arn_parser = ArnParser()
        for arn in self._valid_arns:
            account_id = extract_account_from_arn(arn, arn_parser)
            yield {
                "Id": account_id,
                "Arn": arn,
                "Name": f"Account-{account_id}" if account_id else arn,
            }

    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        try:
            return await self._get_account_session(arn)
        except CredentialsProviderError as e:
            logger.error(
                f"Failed to get session for ARN {arn} due to credentials error: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Failed to get session for ARN {arn} due to session error: {e}"
            )
            raise AWSSessionError(f"Session error for ARN {arn}: {e}") from e

    async def _get_account_session(self, arn: str) -> AioSession:
        return await self._create_and_log_session(arn, session_name="OceanRoleSession")
