from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from loguru import logger
from port_ocean.context.ocean import ocean

StrategyType = SingleAccountStrategy | MultiAccountStrategy


class ResyncStrategyFactory:
    """A factory for creating resync strategies based on the global configuration."""

    @staticmethod
    async def create() -> StrategyType:
        """Create and validate session strategy based on global configuration."""
        config = ocean.integration_config
        is_multi_account = bool(config.get("account_role_arn"))
        provider: CredentialProvider

        if is_multi_account:
            logger.info(
                "[SessionStrategyFactory] Using AssumeRoleProvider for multi-account"
            )
            provider = AssumeRoleProvider()
        else:
            logger.info(
                "[SessionStrategyFactory] Using StaticCredentialProvider (no org role ARN found)"
            )
            provider = (
                StaticCredentialProvider()
            )  # An access key pair is tied to a single IAM user in one AWS account
        strategy_cls: type[SingleAccountStrategy | MultiAccountStrategy] = (
            MultiAccountStrategy if is_multi_account else SingleAccountStrategy
        )

        logger.info(f"Initializing {strategy_cls.__name__}")

        strategy = strategy_cls(provider=provider, config=config)
        _ = await strategy.healthcheck()

        logger.info(f"Successfully initialized {strategy_cls.__name__}")
        return strategy
