from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Set, Optional, Any, Union
import asyncio
from loguru import logger
from aiobotocore.session import AioSession
from botocore.utils import ArnParser

from aws.auth.credentials_provider import CredentialProvider, AssumeRoleProvider
from utils.overrides import AWSDescribeResourcesSelector


def normalize_arn_list(arn_input: Optional[Union[str, List[str]]]) -> List[str]:
    """Return a list of non-empty ARN strings from input (str, list, or None)."""
    if not arn_input:
        return []
    if isinstance(arn_input, str):
        arn_input = [arn_input]
    return [arn.strip() for arn in arn_input if isinstance(arn, str) and arn.strip()]


def extract_account_from_arn(arn: str, arn_parser: ArnParser) -> str:
    """Extract account ID from ARN. Raises if parsing fails."""
    arn_data = arn_parser.parse_arn(arn)
    return arn_data["account"]


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

    def __init__(self, provider: CredentialProvider):
        self.provider = provider

    @abstractmethod
    async def sanity_check(self) -> bool:
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

    async def sanity_check(self) -> bool:
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
        logger.info(f"Validated single account: {identity['Account']}")
        return True

    async def _get_base_session(self) -> AioSession:
        return await self.provider.get_session(region=None)

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            account_id: str = identity["Account"]
        logger.info(f"Accessing single account: {account_id}")
        yield {"Id": account_id, "Arn": identity["Arn"]}

    async def create_session_for_each_account(
        self,
        selector: AWSDescribeResourcesSelector,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        session = await self._get_base_session()
        resolver = RegionResolver(session, selector)
        allowed_regions = list(await resolver.get_allowed_regions())
        for region in allowed_regions:
            yield session, region

    async def create_session_for_account(
        self, arn: str, selector: AWSDescribeResourcesSelector
    ) -> AsyncIterator[tuple[AioSession, str]]:
        session = await self._get_base_session()
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
        session = await self._get_base_session()
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

    def __init__(self, provider: CredentialProvider):

        super().__init__(provider)
        # No role_name needed; we use explicit ARNs
        self._valid_arns: list[str] = []

    async def sanity_check(self) -> bool:
        org_role_arn = self.provider.config.get("organization_role_arn")
        arns = normalize_arn_list(org_role_arn)
        if not arns:
            logger.error("No organization_role_arn(s) provided for sanity check.")
            return False

        self._valid_arns = []
        for arn in arns:
            can_assume = await self._can_assume_role(arn)
            if can_assume:
                logger.info(f"Sanity check passed for ARN {arn}.")
                self._valid_arns.append(arn)
            else:
                logger.error(f"Sanity check failed for ARN {arn}.")
        if not self._valid_arns:
            logger.error(
                "Sanity check failed for all ARNs. No accounts are accessible."
            )
            return False
        return True

    async def _can_assume_role(self, arn: str) -> bool:
        try:
            session = await self.provider.get_session(
                region=None, role_arn=arn, role_session_name="SanityCheckSession"
            )
            async with session.create_client("sts", region_name=None) as sts:
                identity = await sts.get_caller_identity()
                logger.debug(
                    f"Assumed role {arn} as {identity['Arn']} for sanity check."
                )
            return True
        except Exception as e:
            logger.error(f"Failed to assume role for ARN {arn}: {e}")
            return False

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        # Only use ARNs that passed sanity check
        arn_parser = ArnParser()
        for arn in self._valid_arns:
            account_id = extract_account_from_arn(arn, arn_parser)
            account = {
                "Id": account_id,
                "Arn": arn,
                "Name": f"Account-{account_id}" if account_id else arn,
            }
            yield account

    async def create_session_for_each_account(
        self,
        selector: AWSDescribeResourcesSelector,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        accessible_accounts = []
        async for account in self.get_accessible_accounts():
            accessible_accounts.append(account)
        total_accounts = len(accessible_accounts)

        async def process_account_regions(
            account: dict[str, Any], account_index: int
        ) -> list[tuple[AioSession, str]]:
            logger.info(
                f"[Account {account_index+1}/{total_accounts}] Creating session for ARN {account['Arn']}"
            )
            session: Optional[AioSession] = None
            session = await self._get_account_session(account["Arn"])
            if session is None:
                logger.warning(
                    f"Session not created for ARN {account['Arn']}. Skipping regions."
                )
                return []
            resolver = RegionResolver(session, selector)
            allowed_regions = list(await resolver.get_allowed_regions())
            if not allowed_regions:
                logger.warning(
                    f"No allowed regions for ARN {account['Arn']}. Skipping account."
                )
                return []
            logger.info(
                f"[ARN {account['Arn']}] Using session for regions: {allowed_regions} (total: {len(allowed_regions)})"
            )
            results = [(session, region) for region in allowed_regions]
            return results

        tasks = [
            process_account_regions(account, idx)
            for idx, account in enumerate(accessible_accounts)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                for session_region_tuple in result:
                    yield session_region_tuple
            elif isinstance(result, Exception):
                logger.error(f"Account processing failed: {result}")

    async def create_session_for_account(
        self, arn: str, selector: AWSDescribeResourcesSelector
    ) -> AsyncIterator[tuple[AioSession, str]]:
        # Only allow session creation for ARNs that passed sanity check
        if arn not in self._valid_arns:
            logger.warning(f"ARN {arn} did not pass sanity check and will be skipped.")
            return
        try:
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
        except Exception as e:
            logger.error(f"Failed to create sessions for ARN {arn}: {str(e)}")

    async def get_account_session(self, arn: str) -> Optional[AioSession]:
        """Get a single session for a specific ARN (MultiAccountStrategy)."""
        try:
            return await self._get_account_session(arn)
        except Exception as e:
            logger.error(f"Failed to get session for ARN {arn}: {str(e)}")
            return None

    async def _get_account_session(self, arn: str) -> AioSession:
        # Use the provided ARN directly for AssumeRole
        session = await self.provider.get_session(
            region=None, role_arn=arn, role_session_name="RoleSessionName"
        )
        # Log the assumed role identity
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            logger.info(f"Successfully assumed role: {arn} as {identity['Arn']}")
        return session
