from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.base import AWSSessionStrategy
from loguru import logger
from port_ocean.context.ocean import ocean
from typing import Optional
from aws.auth.utils import normalize_arn_list


class SessionStrategyFactory:
    """An access key pair is tied to a single IAM user in one AWS account"""

    @staticmethod
    async def create(
        provider: Optional[CredentialProvider] = None,
    ) -> AWSSessionStrategy:
        """Create and validate session strategy based on global configuration."""
        config = ocean.integration_config
        is_multi_account = bool(config.get("account_role_arn"))
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
        strategy_cls: type[AWSSessionStrategy] = (
            MultiAccountStrategy if is_multi_account else SingleAccountStrategy
        )

        logger.info(f"Initializing {strategy_cls.__name__}")

        if strategy_cls == MultiAccountStrategy:
            org_role_arns = normalize_arn_list(config.get("account_role_arn"))

            logger.info(
                f"Configuration: org_role_arns={org_role_arns}, "
                f"account_read_role_name={config.get('account_read_role_name')}"
            )

        strategy = strategy_cls(provider=provider, config=config)

        logger.info(f"Successfully initialized {strategy_cls.__name__}")
        return strategy
