from aws.auth.strategies.organizations_strategy import OrganizationsStrategy
from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from loguru import logger
from port_ocean.context.ocean import ocean
from aiobotocore.session import AioSession
from typing import Any, TypedDict, AsyncIterator
from aws.auth.providers.assume_role_with_web_identity_provider import (
    AssumeRoleWithWebIdentityProvider,
)
import os

StrategyType = SingleAccountStrategy | MultiAccountStrategy | OrganizationsStrategy


class ResyncStrategyFactory:
    """A factory for creating resync strategies based on the global configuration."""

    _cached_strategy: StrategyType | None = None

    @classmethod
    def _detect_provider_type(cls, config: dict[str, Any]) -> CredentialProvider:
        """
        Detect the appropriate provider type based on environment variables and config.
        Returns a tuple of (provider_instance, provider_type_name, strategy_class)
        """

        # Check for web identity token first (highest priority)
        if os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"):
            logger.info(
                "[SessionStrategyFactory] Using AssumeRoleWithWebIdentityProvider (found AWS_WEB_IDENTITY_TOKEN_FILE)"
            )
            return AssumeRoleWithWebIdentityProvider(config=config)

        logger.info("[SessionStrategyFactory] Using AssumeRoleProvider")
        return AssumeRoleProvider(config=config)

    @classmethod
    async def create(cls) -> StrategyType:
        if cls._cached_strategy is not None:
            return cls._cached_strategy
        config = ocean.integration_config or {}
        account_role_arn = config.get("account_role_arn")
        is_multi_account = bool(account_role_arn and len(account_role_arn) > 0)

        provider: CredentialProvider
        strategy_cls: type[StrategyType]

        if is_multi_account:
            logger.info("[SessionStrategyFactory] Using MultiAccountStrategy")
            provider = cls._detect_provider_type(config=config)
            # strategy_cls = MultiAccountStrategy
            strategy_cls = OrganizationsStrategy
        else:
            logger.info(
                "[SessionStrategyFactory] Using StaticCredentialProvider (no org role ARN found)"
            )
            provider = StaticCredentialProvider(config=config)
            strategy_cls = SingleAccountStrategy

        logger.info(f"Initializing {strategy_cls.__name__}")
        strategy = strategy_cls(provider=provider, config=config)
        logger.info(f"Successfully initialized {strategy_cls.__name__}")

        cls._cached_strategy = strategy
        return strategy


class AccountInfo(TypedDict):
    Id: str
    Name: str


async def get_all_account_sessions() -> AsyncIterator[tuple[AccountInfo, AioSession]]:
    strategy = await ResyncStrategyFactory.create()
    async for account_info, session in strategy.get_account_sessions():
        yield AccountInfo(Id=account_info["Id"], Name=account_info["Name"]), session
