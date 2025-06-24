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
from typing import Any, Optional, Union

from utils.overrides import AWSResourceConfig


def normalize_arn_list(arn_input: Optional[Union[str, list[str]]]) -> list[str]:
    """Normalize ARN input to a list of strings, filtering out empty values."""
    if not arn_input:
        return []

    if isinstance(arn_input, str):
        return [arn_input] if arn_input.strip() else []

    if isinstance(arn_input, list):
        return [
            arn for arn in arn_input if arn and isinstance(arn, str) and arn.strip()
        ]


class SessionStrategyFactory:
    """Factory for creating appropriate AWS session strategies."""

    @staticmethod
    async def create(
        provider: Optional[CredentialProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> AWSSessionStrategy:
        """Create and validate session strategy based on configuration."""
        if config is None:
            from port_ocean.context.ocean import ocean

            config = ocean.integration_config

        if provider is None:
            if config.get("organization_role_arn"):
                logger.info(
                    "[SessionStrategyFactory] Using AssumeRoleProvider for multi-account"
                )
                provider = AssumeRoleProvider(config=config)
            else:
                logger.info(
                    "[SessionStrategyFactory] Using StaticCredentialProvider (no org role ARN found)"
                )
                provider = StaticCredentialProvider(config=config)

        strategy_cls = (
            MultiAccountStrategy
            if config.get("account_read_role_name")
            and config.get("organization_role_arn")
            else SingleAccountStrategy
        )

        logger.info(f"Initializing {strategy_cls.__name__}")

        if strategy_cls == MultiAccountStrategy:
            org_role_arns = normalize_arn_list(config.get("organization_role_arn"))

            logger.info(
                f"Configuration: org_role_arns={org_role_arns}, "
                f"account_read_role_name={config.get('account_read_role_name')}, "
                f"target_account_ids={config.get('target_account_ids', [])}"
            )

        strategy = strategy_cls(provider=provider)

        logger.info(f"Successfully initialized {strategy_cls.__name__}")
        return strategy
