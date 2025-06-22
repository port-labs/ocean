from aws.auth.credentials_provider import (
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


class SessionStrategyFactory:
    def __init__(self, provider=None):
        self.provider = provider

    @property
    def _has_multi_account_config(self) -> bool:
        org_role_arn = ocean.integration_config.get("organization_role_arn")
        account_read_role = ocean.integration_config.get("account_read_role_name")
        return org_role_arn and account_read_role

    async def __call__(self, **kwargs) -> AWSSessionStrategy:
        # Use provided provider or create new one based on config
        if self.provider is not None:
            provider = self.provider
            logger.debug("Using provided credentials provider")
        else:
            # Fallback to creating new provider (for backward compatibility)
            provider = (
                AssumeRoleProvider(config=ocean.integration_config)
                if self._has_multi_account_config
                else StaticCredentialProvider(config=ocean.integration_config)
            )
            logger.info("Created new credentials provider")

        if self._has_multi_account_config:
            strategy = MultiAccountStrategy(provider=provider, **kwargs)
            if await strategy.sanity_check():
                return strategy
            logger.warning("Multi-account denied. Falling back to single-account.")

        single_strategy = SingleAccountStrategy(provider=provider, **kwargs)
        if await single_strategy.sanity_check():
            return single_strategy
        logger.error(
            "Single account strategy sanity check failed. Unable to initialize AWS session strategy."
        )
        raise RuntimeError("No valid AWS session strategy could be initialized.")
