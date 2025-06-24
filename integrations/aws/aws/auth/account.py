from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Set, Optional, Any, Tuple, Union
import asyncio
from loguru import logger
import aioboto3
from aiobotocore.session import AioSession
import re
from botocore.utils import ArnParser

from aws.auth.credentials_provider import CredentialProvider
from utils.overrides import AWSResourceConfig, AWSDescribeResourcesSelector


def normalize_arn_list(arn_input: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize ARN input to a list of strings, filtering out empty values."""
    if not arn_input:
        return []

    if isinstance(arn_input, str):
        return [arn_input] if arn_input.strip() else []

    if isinstance(arn_input, list):
        return [
            arn for arn in arn_input if arn and isinstance(arn, str) and arn.strip()
        ]


def extract_account_from_arn(arn: str, arn_parser: ArnParser) -> Optional[str]:
    """Extract account ID from ARN with proper error handling."""
    try:
        arn_data = arn_parser.parse_arn(arn)
        return arn_data.get("account")
    except Exception as e:
        logger.warning(f"Failed to parse ARN '{arn}': {e}")
        return None


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
    async def create_session_for_each_region(
        self,
        resource_config: AWSResourceConfig,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """Create a single session and yield it with each allowed region."""
        yield  # type: ignore [misc]

    @abstractmethod
    async def create_session_for_account(
        self, account_id: str, resource_config: AWSResourceConfig
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """Create a single session for a specific account with each allowed region."""
        yield  # type: ignore [misc]

    @abstractmethod
    async def get_account_session(self, account_id: str) -> Optional[AioSession]:
        """Get a single session for a specific account."""
        pass


class SingleAccountStrategy(AWSSessionStrategy):
    """Strategy for handling a single AWS account."""

    async def sanity_check(self) -> bool:
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
        logger.info(f"Validated single account: {identity['Account']}")
        return True

    async def _get_role_arn(self, session: AioSession) -> Optional[str]:
        # Preconditions: role_name is set and provider is refreshable
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            account_id: str = identity["Account"]
        role_name: str = self.provider.config["account_read_role_name"]
        return f"arn:aws:iam::{account_id}:role/{role_name}"

    async def _get_base_session(self) -> AioSession:
        session = await self.provider.get_session(region=None)
        role_name = (
            self.provider.config["account_read_role_name"]
            if "account_read_role_name" in self.provider.config
            else None
        )
        if role_name and self.provider.is_refreshable:
            role_arn = await self._get_role_arn(session)
            if role_arn:
                return await self.provider.get_session(
                    region=None, role_arn=role_arn, role_session_name="RoleSessionName"
                )
        return session

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        if not await self.sanity_check():
            return
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            account_id: str = identity["Account"]
        logger.info(f"Accessing single account: {account_id}")
        yield {"Id": account_id, "Arn": identity["Arn"]}

    async def create_session_for_each_region(
        self,
        resource_config: AWSResourceConfig,
    ) -> AsyncIterator[Tuple[AioSession, str]]:
        """Create a single session and yield it with each allowed region."""
        if not await self.sanity_check():
            return
        session = await self._get_base_session()
        resolver = RegionResolver(session, resource_config.selector)
        allowed_regions = await resolver.get_allowed_regions()

        for region in allowed_regions:
            yield session, region

    async def create_session_for_account(
        self, account_id: str, resource_config: AWSResourceConfig
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """Create a single session for a specific account with each allowed region."""
        if not await self.sanity_check():
            return
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            current_account_id: str = identity["Account"]
        if current_account_id != account_id:
            logger.warning(
                f"Requested account {account_id} does not match current account {current_account_id}"
            )
            return
        async for session_region_tuple in self.create_session_for_each_region(
            resource_config
        ):
            yield session_region_tuple

    async def get_account_session(self, account_id: str) -> Optional[AioSession]:
        """Get a single session for a specific account."""
        if not await self.sanity_check():
            return None
        session = await self._get_base_session()
        async with session.create_client("sts", region_name=None) as sts:
            identity = await sts.get_caller_identity()
            current_account_id: str = identity["Account"]
        if current_account_id != account_id:
            logger.warning(
                f"Requested account {account_id} does not match current account {current_account_id}"
            )
            return None
        return session


class MultiAccountStrategy(AWSSessionStrategy):
    """Strategy for handling multiple AWS accounts."""

    async def sanity_check(self) -> bool:
        logger.info(
            "[MultiAccountStrategy] Skipping org role sanity check (using provided ARNs)"
        )
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        org_role_arn = (
            self.provider.config["organization_role_arn"]
            if "organization_role_arn" in self.provider.config
            else None
        )
        arn_parser = ArnParser()

        arns = normalize_arn_list(org_role_arn)

        for arn in arns:
            account_id = extract_account_from_arn(arn, arn_parser)
            if account_id:
                yield {"Id": account_id, "Arn": arn, "Name": f"Account-{account_id}"}
            else:
                logger.warning(f"Could not parse account ID from ARN: {arn}")

    async def create_session_for_each_region(
        self,
        resource_config: AWSResourceConfig,
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """Create sessions for each account with their allowed regions."""
        if not await self.sanity_check():
            return
        accessible_accounts = []
        async for account in self.get_accessible_accounts():
            accessible_accounts.append(account)

        total_accounts = len(accessible_accounts)

        async def process_account_regions(
            account: dict[str, Any],
            account_index: int,
        ) -> list[tuple[AioSession, str]]:
            logger.info(
                f"[Account {account_index+1}/{total_accounts}] Creating session for account {account['Id']}"
            )
            session: Optional[AioSession] = None
            session = await self._get_account_session(account["Id"])
            if session is None:
                logger.warning(
                    f"Session not created for account {account['Id']}. Skipping regions."
                )
                return []

            resolver = RegionResolver(
                session, resource_config.selector, account_id=account["Id"]
            )
            allowed_regions = await resolver.get_allowed_regions()
            region_list = sorted(list(allowed_regions))
            total_regions = len(region_list)
            logger.info(
                f"[Account {account['Id']}] Using session for allowed regions: {region_list} (total: {total_regions})"
            )
            results = [(session, region) for region in region_list]
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
        self, account_id: str, resource_config: AWSResourceConfig
    ) -> AsyncIterator[tuple[AioSession, str]]:
        """Create a single session for a specific account with each allowed region."""
        if not await self.sanity_check():
            return
        is_accessible = False
        async for account in self.get_accessible_accounts():
            if account["Id"] == account_id:
                is_accessible = True
                break
        if not is_accessible:
            logger.warning(f"Account {account_id} not accessible")
            return
        try:
            logger.info(f"Creating session for account {account_id}")
            session = await self._get_account_session(account_id)
            resolver = RegionResolver(
                session, resource_config.selector, account_id=account_id
            )
            allowed_regions = await resolver.get_allowed_regions()
            region_list = sorted(list(allowed_regions))
            total_regions = len(region_list)
            logger.info(
                f"[Account {account_id}] Using session for allowed regions: {region_list} (total: {total_regions})"
            )
            for region in region_list:
                yield session, region

        except Exception as e:
            logger.error(
                f"Failed to create sessions for account {account_id}: {str(e)}"
            )

    async def get_account_session(self, account_id: str) -> Optional[AioSession]:
        """Get a single session for a specific account."""
        if not await self.sanity_check():
            return None
        try:
            return await self._get_account_session(account_id)
        except Exception as e:
            logger.error(f"Failed to get session for account {account_id}: {str(e)}")
            return None

    async def _get_account_session(self, account_id: str) -> AioSession:
        role_name: Optional[str] = (
            self.provider.config["account_read_role_name"]
            if "account_read_role_name" in self.provider.config
            else None
        )
        if not role_name:
            logger.warning("No account_read_role_name configured")
            return None
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        return await self.provider.get_session(
            region=None, role_arn=role_arn, role_session_name="RoleSessionName"
        )
