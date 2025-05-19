from aws.auth.credentials_provider import (
    AssumeRoleProvider,
    StaticCredentialProvider,
)
from aws.auth.c import (
    MultiAccountStrategy,
    SingleAccountStrategy,
)
from loguru import logger
from port_ocean.context.ocean import ocean


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
