from aws.auth.credentials_provider import (
    CredentialProvider,
    AssumeRoleProvider,
    StaticCredentialProvider,
)
from aws.auth.account import (
    MultiAccountStrategy,
    SingleAccountStrategy,
    AWSSessionStrategy,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from typing import Optional
from aws.auth.utils import normalize_arn_list


class SessionStrategyFactory:
    """Factory for creating appropriate AWS session strategies."""

    @staticmethod
    async def create(
        provider: Optional[CredentialProvider] = None,
    ) -> AWSSessionStrategy:
        """Create and validate session strategy based on global configuration."""
        config = ocean.integration_config
        is_multi_account = bool(config.get("organization_role_arn"))
        if is_multi_account:
            logger.info(
                "[SessionStrategyFactory] Using AssumeRoleProvider for multi-account"
            )
            provider = AssumeRoleProvider(config=config)
        else:
            logger.info(
                "[SessionStrategyFactory] Using StaticCredentialProvider (no org role ARN found)"
            )
            provider = StaticCredentialProvider(config=config)
        strategy_cls: type[AWSSessionStrategy] = (
            MultiAccountStrategy if is_multi_account else SingleAccountStrategy
        )

        logger.info(f"Initializing {strategy_cls.__name__}")

        if strategy_cls == MultiAccountStrategy:
            org_role_arns = normalize_arn_list(config.get("organization_role_arn"))

            logger.info(
                f"Configuration: org_role_arns={org_role_arns}, "
                f"account_read_role_name={config.get('account_read_role_name')}"
            )

        strategy = strategy_cls(provider=provider)

        logger.info(f"Successfully initialized {strategy_cls.__name__}")
        return strategy
