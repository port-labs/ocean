from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Set, Optional, Any
import asyncio
from loguru import logger
from aiobotocore.session import AioSession
from botocore.utils import ArnParser

from aws.auth.credentials_provider import CredentialProvider
from aws.auth.utils import (
    normalize_arn_list,
    extract_account_from_arn,
    AWSSessionError,
    CredentialsProviderError,
)
from utils.overrides import AWSDescribeResourcesSelector


class RegionResolver:
    """Handles AWS region discovery and filtering."""

    def __init__(
        self,
        session: AioSession,
        selector: AWSDescribeResourcesSelector,
        account_id: Optional[str] = None,
    ):
        self.session = session
        self.selector = selector
        self.account_id = account_id

    async def get_enabled_regions(self) -> List[str]:
        """Retrieve enabled AWS regions."""
        async with self.session.create_client("account", region_name=None) as client:
            response = await client.list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )
            regions = [region["RegionName"] for region in response.get("Regions", [])]
            logger.debug(f"Retrieved enabled regions: {regions}")
            return regions

    async def get_allowed_regions(self) -> Set[str]:
        """Filter enabled regions based on selector configuration."""
        enabled_regions = await self.get_enabled_regions()
        allowed_regions = {
            region
            for region in enabled_regions
            if self.selector.is_region_allowed(region)
        }

        return allowed_regions


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Verify strategy configuration and connectivity."""
        pass

    @abstractmethod
    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        """Yield accessible AWS accounts."""
        yield  # type: ignore [misc]

    @abstractmethod
    async def create_session_for_each_account(
        self,
        selector: AWSDescribeResourcesSelector,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """For each account, discover allowed regions and yield (session, region)."""
        yield  # type: ignore [misc]

    @abstractmethod
    async def create_session_for_account(
        self, arn: str, selector: AWSDescribeResourcesSelector
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """For a specific ARN, discover allowed regions and yield (session, region)."""
        yield  # type: ignore [misc]

    @abstractmethod
    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        """Get a single session for a specific ARN."""
        pass


class SingleAccountStrategy(AWSSessionStrategy):
    """Strategy for handling a single AWS account."""

    async def healthcheck(self) -> bool:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
        logger.info(f"Validated single account: {identity['Account']}")
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            account_id: str = identity["Account"]
        logger.info(f"Accessing single account: {account_id}")
        yield {"Id": account_id, "Arn": identity["Arn"]}

    async def create_session_for_each_account(
        self,
        selector: AWSDescribeResourcesSelector,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        session = await self.provider.get_session(region=None)
        resolver = RegionResolver(session, selector)
        allowed_regions = list(await resolver.get_allowed_regions())
        for region in allowed_regions:
            yield session, region

    async def create_session_for_account(
        self, arn: str, selector: AWSDescribeResourcesSelector
    ) -> AsyncIterator[tuple[AioSession, str]]:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            current_arn: str = identity["Arn"]
        if current_arn != arn:
            logger.warning(
                f"Requested ARN {arn} does not match current ARN {current_arn}"
            )
            return
        resolver = RegionResolver(session, selector)
        allowed_regions = list(await resolver.get_allowed_regions())
        for region in allowed_regions:
            yield session, region

    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        """Get a single session for a specific ARN (SingleAccountStrategy)."""
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
                    f"Sanity check failed for ARN {arn} due to exception: {result}"
                )
                continue
            if result:
                logger.info(f"Sanity check passed for ARN {arn}.")
                self._valid_arns.append(arn)
            else:
                logger.warning(f"Sanity check failed for ARN {arn}.")

        if not self._valid_arns:
            logger.error(
                "Health check failed for all ARNs. No accounts are accessible."
            )
            raise AWSSessionError(  # TODO: raise a custom exception
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
            session = await self._create_and_log_session(
                arn, session_name="SanityCheckSession"
            )
            return True
        except CredentialsProviderError as e:
            logger.error(
                f"Failed to assume role for ARN {arn} due to credentials error: {e}"
            )
            return False

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        # Only use ARNs that passed healthcheck
        arn_parser = ArnParser()
        for arn in self._valid_arns:
            account_id = extract_account_from_arn(arn, arn_parser)
            yield {
                "Id": account_id,
                "Arn": arn,
                "Name": f"Account-{account_id}" if account_id else arn,
            }

    async def create_session_for_each_account(
        self,
        selector: AWSDescribeResourcesSelector,
    ) -> AsyncIterator[tuple[AioSession, str]]:

        async def process_account_regions(
            account_info: dict[str, Any]
        ) -> list[tuple[AioSession, str]]:

            session = await self._get_account_session(account_info["Arn"])
            resolver = RegionResolver(session, selector)
            allowed_regions = await resolver.get_allowed_regions()
            if not allowed_regions:
                logger.warning(
                    f"No allowed regions for ARN {account_info['Arn']}. Skipping account."
                )
                return []
            logger.info(
                f"[ARN {account_info['Arn']}] Using session for regions: {allowed_regions} (total: {len(allowed_regions)})"
            )
            results = [(session, region) for region in allowed_regions]
            return results

        tasks = [
            process_account_regions(account_info)
            async for account_info in self.get_accessible_accounts()
        ]

        results = await asyncio.gather(*tasks)
        for result in results:
            for session, region in result:
                yield session, region

    async def create_session_for_account(
        self, arn: str, selector: AWSDescribeResourcesSelector
    ) -> AsyncIterator[tuple[AioSession, str]]:
        # Only allow session creation for ARNs that passed health check
        if arn not in self._valid_arns:
            logger.warning(f"ARN {arn} did not pass health check, skipping...")
            return

        logger.info(f"Creating session for ARN {arn}")
        session = await self._get_account_session(arn)
        resolver = RegionResolver(session, selector)
        allowed_regions = list(await resolver.get_allowed_regions())
        if not allowed_regions:
            logger.warning(f"No allowed regions for ARN {arn}. Skipping.")
            return
        logger.info(
            f"[ARN {arn}] Using session for regions: {allowed_regions} (total: {len(allowed_regions)})"
        )
        for region in allowed_regions:
            yield session, region

    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        """Get a single session for a specific ARN (MultiAccountStrategy)."""
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
