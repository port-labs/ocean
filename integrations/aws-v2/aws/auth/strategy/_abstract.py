from abc import ABC, abstractmethod
from typing import AsyncIterator, Tuple
from aiobotocore.session import AioSession
from auth.credentials_provider import CredentialProvider
from overrides import AWSResourceConfig

from typing import List, Set


class RegionResolver:
    def __init__(self, session: AioSession, selector: AWSResourceConfig):
        self.session = session
        self.selector = selector

    async def get_enabled_regions(self) -> List[str]:
        async with self.session.create_client("account") as client:
            response = await client.list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )
            return [region["RegionName"] for region in response.get("Regions", [])]

    async def get_allowed_regions(self) -> Set[str]:
        enabled_regions = await self.get_enabled_regions()
        return {
            region
            for region in enabled_regions
            if self.selector.is_region_allowed(region)
        }


class AbstractStrategy(ABC):
    def __init__(self, provider: CredentialProvider, selector: AWSResourceConfig):
        self.provider = provider
        self.selector = selector

    @abstractmethod
    async def sanity_check(self) -> bool:
        pass

    @abstractmethod
    async def get_accessible_accounts(self) -> AsyncIterator[Tuple[str, AioSession]]:
        pass

    @abstractmethod
    async def create_session_for_each_region(self) -> AsyncIterator[AioSession]:
        pass

    async def check_permission(
        self, session: AioSession, arn: str, action: str, resource: str
    ) -> bool:
        async with session.create_client("iam") as client:
            response = await client.simulate_principal_policy(
                PolicySourceArn=arn, ActionNames=[action], ResourceArns=[resource]
            )
            decision = response["EvaluationResults"][0]["EvalDecision"]
            return decision.lower() == "allowed"
