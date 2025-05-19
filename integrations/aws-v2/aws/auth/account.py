from auth.credentials_provider import (
    CredentialProvider,
    AssumeRoleProvider,
    StaticCredentialProvider,
)

from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.context.ocean import ocean
import asyncio
from typing import List, Set
from overrides import AWSResourceConfig
from port_ocean.context.event import event

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List, Set
from auth.credentials_provider import CredentialProvider
from aiobotocore.session import AioSession
from loguru import logger
from overrides import AWSResourceConfig
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class RegionResolver:
    def __init__(self, session: AioSession, selector):
        self.session = session
        self.selector = selector

    async def get_enabled_regions(self) -> List[str]:
        try:
            async with self.session.create_client("account") as client:
                response = await client.list_regions(
                    RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
                )
                return [region["RegionName"] for region in response.get("Regions", [])]
        except Exception as e:
            logger.warning(f"Region fetch failed: {e}")
            return []

    async def get_allowed_regions(self) -> Set[str]:
        enabled = await self.get_enabled_regions()
        return set(
            region for region in enabled if self.selector.is_region_allowed(region)
        )


class AWSSessionStrategy(ABC):
    def __init__(
        self, provider: CredentialProvider, selector: AWSResourceConfig, **kwargs: Any
    ):
        self.provider = provider
        self.selector = selector
        self.kwargs = kwargs

    @abstractmethod
    async def sanity_check(self) -> bool: ...

    @abstractmethod
    async def get_accessible_accounts(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]: ...

    async def check_permission(
        self, session: AioSession, arn: str, action: str, resource: str
    ) -> bool:
        async with session.create_client("iam") as client:
            response = await client.simulate_principal_policy(
                PolicySourceArn=arn, ActionNames=[action], ResourceArns=[resource]
            )
            return response["EvaluationResults"][0]["EvalDecision"] == "allowed"


class SingleAccountStrategy(AWSSessionStrategy):
    async def sanity_check(self) -> bool:
        return True

    async def get_accessible_accounts(self) -> AsyncIterator[dict]:
        session = await self.provider.get_session(region=None)
        async with session.create_client("sts") as sts:
            identity = await sts.get_caller_identity()
            account_id = identity["Account"]
            response = await sts.describe_account(AccountId=account_id)
            yield response["Account"]

    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]:
        session = await self.provider.get_session(region=None)
        region_resolver = RegionResolver(session, self.selector)
        allowed_regions = await region_resolver.get_allowed_regions()
        for region in allowed_regions:
            yield await self.provider.get_session(region=region)


class MultiAccountStrategy(AWSSessionStrategy):
    async def sanity_check(self) -> bool:
        try:
            session = await self.get_org_session()
            return all(
                [
                    await self.check_permission(
                        session,
                        self.provider.config["organization_role_arn"],
                        "sts:AssumeRole",
                        self.provider.config["organization_role_arn"],
                    ),
                    await self.check_permission(
                        session,
                        self.provider.config["organization_role_arn"],
                        "organizations:ListAccounts",
                        "arn:aws:organizations:::organization/*",
                    ),
                ]
            )
        except Exception as e:
            logger.warning(f"Multi-account sanity check failed: {e}")
            return False

    async def get_org_session(self) -> AioSession:
        if not (self.provider.config["organization_role_arn"]):
            logger.warning(
                "Did not specify organization role ARN, assuming application session has access to organization accounts."
            )
            return self.provider._session
        return await self.provider.get_session(
            region=None,
            role_arn=self.provider.config["organization_role_arn"],
            role_session_name=self.provider.config["role_session_name"],
        )

    async def get_accessible_accounts(self) -> AsyncIterator[dict[str, Any]]:
        session = await self.get_org_session()
        async with session.create_client("organizations") as org:
            paginator = org.get_paginator("list_accounts")
            async for page in paginator.paginate():
                accounts = page["Accounts"]
                tasks = []
                for acct in accounts:
                    role_arn = f"arn:aws:iam::{acct['Id']}:role/{self.provider.config["account_read_role_name"]}"
                    test_session = await self.provider.get_session(
                        region=None, role_arn=role_arn
                    )
                    tasks.append(
                        self.check_permission(
                            test_session, role_arn, "sts:AssumeRole", role_arn
                        )
                    )

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for acct, result in zip(accounts, results):
                    if isinstance(result, Exception):
                        logger.warning(f"Skipping account {acct['Id']}: {result}")
                        continue
                    if result:
                        yield acct

    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]:
        async for account in self.get_accessible_accounts():
            role_arn = f"arn:aws:iam::{account['Id']}:role/{self.provider.config['account_read_role_name']}"
            session = await self.provider.get_session(role_arn=role_arn, region=None)
            region_resolver = RegionResolver(session, self.selector)
            allowed_regions = await region_resolver.get_allowed_regions()
            for region in allowed_regions:
                yield await self.provider.get_session(role_arn=role_arn, region=region)


class SessionStrategyFactory:
    def __init__(self, provider: CredentialProvider):
        self.provider = provider

    @property
    def _has_multi_account_config(self) -> bool:
        org_role_arn = ocean.integration_config.get("organization_role_arn")
        account_read_role = ocean.integration_config.get("account_read_role_name")
        return org_role_arn and account_read_role

    async def __call__(self, **kwargs) -> AWSSessionStrategy:

        if self._has_multi_account_config:
            logger.info("Attempting multi-account session strategy.")
            strategy = MultiAccountStrategy(
                provider=AssumeRoleProvider(config=ocean.integration_config), **kwargs
            )
            if await strategy.sanity_check():
                logger.info("✅ Multi-account access confirmed.")
                return strategy
            logger.warning("❌ Multi-account denied. Falling back to single-account.")

        logger.info("Using single-account session strategy.")
        return SingleAccountStrategy(
            provider=StaticCredentialProvider(config=ocean.integration_config), **kwargs
        )
