from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_credentials_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from loguru import logger
from port_ocean.context.ocean import ocean
from typing import AsyncIterator
from aws.auth._helpers.exceptions import ResyncStrategyError
from aws.auth.strategies.base import AccountContext


StrategyType = SingleAccountStrategy | MultiAccountStrategy


class ResyncStrategyFactory:
    """A factory for creating resync strategies based on the global configuration."""

    _cached_strategy: StrategyType | None = None

    @classmethod
    async def create(cls) -> StrategyType:
        if cls._cached_strategy is not None:
            return cls._cached_strategy
        config = ocean.integration_config or {}
        account_role_arn = config.get("account_role_arn")
        is_multi_account = bool(account_role_arn and len(account_role_arn) > 0)
        is_single_account = bool(
            config.get("aws_access_key_id") and config.get("aws_secret_access_key")
        )

        provider: CredentialProvider
        strategy_cls: type[StrategyType]

        if is_multi_account:
            logger.info(
                "[SessionStrategyFactory] Using AssumeRoleProvider for multi-account"
            )
            provider = AssumeRoleProvider(config=config)
            strategy_cls = MultiAccountStrategy
        elif is_single_account:
            logger.info(
                "[SessionStrategyFactory] Using StaticCredentialProvider (no org role ARN found)"
            )
            provider = StaticCredentialProvider(config=config)
            strategy_cls = SingleAccountStrategy

        else:
            raise ResyncStrategyError(
                "Unable to create a resync strategy: No valid AWS credentials found for either multi-account (account_role_arn) or single-account (access_key_id/secret_access_key) configuration."
            )

        logger.info(f"Initializing {strategy_cls.__name__}")
        strategy = strategy_cls(provider=provider, config=config)
        logger.info(f"Successfully initialized {strategy_cls.__name__}")

        cls._cached_strategy = strategy
        return strategy


async def get_all_account_sessions() -> AsyncIterator[AccountContext]:
    strategy = await ResyncStrategyFactory.create()
    async for account_context in strategy.get_account_sessions():
        yield account_context
