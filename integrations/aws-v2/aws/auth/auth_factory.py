from auth.credentials_provider import (
    AssumeRoleProvider,
    StaticCredentialProvider,
)

from loguru import logger
from port_ocean.context.ocean import ocean
from overrides import AWSResourceConfig
from auth.strategy.multi_account import MultiAccountStrategy
from auth.strategy.single_account import SingleAccountStrategy
from auth.strategy._abstract import AbstractStrategy


class AuthFactory:
    """
    Note: Static credentials (IAM User) are not recommended for multi-account setups,
    but assume role can be used for both single and multi-account configurations
    """

    @staticmethod
    async def create(selector: AWSResourceConfig) -> AbstractStrategy:
        integration_config = ocean.integration_config
        provider = (
            AssumeRoleProvider(config=integration_config)
            if integration_config.get("account_read_role_arns")
            else StaticCredentialProvider(config=integration_config)
        )

        strategy_cls = (
            MultiAccountStrategy
            if integration_config.get("account_read_role_arns")
            else SingleAccountStrategy
        )
        strategy = strategy_cls(provider=provider, selector=selector)

        if await strategy.sanity_check():
            return strategy

        raise ValueError(
            "Failed to create a valid authentication strategy."
        )  # TODO: For self-hosted, fallback to single account strategy allowing boto3 toolchain to figure out the right credentials
