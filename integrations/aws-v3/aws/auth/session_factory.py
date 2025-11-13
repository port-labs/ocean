from aws.auth.strategies.organizations_strategy import OrganizationsStrategy
from aws.auth.providers.base import CredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from loguru import logger
from port_ocean.context.ocean import ocean
from aiobotocore.session import AioSession
from typing import Any, TypedDict, AsyncIterator, Dict
from aws.auth.providers.assume_role_with_web_identity_provider import (
    AssumeRoleWithWebIdentityProvider,
)
import os

StrategyType = SingleAccountStrategy | MultiAccountStrategy | OrganizationsStrategy

DEFAULT_PROVIDER_PRIORITY: str = "AssumeRoleWithWebIdentity,StaticCredential,AssumeRole"


class AccountStrategyFactory:
    """A factory for creating account strategies based on the global configuration."""

    _cached_strategy: StrategyType | None = None

    _provider_factories: Dict[str, type[CredentialProvider]] = {
        "AssumeRoleWithWebIdentity": AssumeRoleWithWebIdentityProvider,
        "StaticCredential": StaticCredentialProvider,
        "AssumeRole": AssumeRoleProvider,
    }

    @classmethod
    def _get_provider_priority(cls, config: dict[str, Any]) -> list[str]:
        """
        Returns the credential provider priority list, falling back to DEFAULT_PROVIDER_PRIORITY if not provided.
        Example: "AssumeRoleWithWebIdentity,StaticCredential,AssumeRole"
        """
        priority_str = (
            config.get("credential_provider_priority") or DEFAULT_PROVIDER_PRIORITY
        )
        return [
            provider.strip() for provider in priority_str.split(",") if provider.strip()
        ]

    @classmethod
    def _detect_provider_type(cls, config: dict[str, Any]) -> CredentialProvider:
        """
        Dynamically detect the appropriate provider type based on the configured priority.
        """
        for provider_name in cls._get_provider_priority(config):
            provider_cls = cls._provider_factories.get(provider_name)
            if not provider_cls:
                logger.warning(
                    f"[AccountStrategyFactory] Unknown provider '{provider_name}', skipping..."
                )
                continue

            if cls._provider_is_applicable(provider_name, config):
                logger.info(
                    f"[AccountStrategyFactory] Using {provider_cls.__name__} (priority: {provider_name})"
                )
                return provider_cls(config=config)

        # Fallback: use AssumeRole if none matched
        logger.warning(
            "[AccountStrategyFactory] No valid provider found; falling back to AssumeRoleProvider"
        )
        return AssumeRoleProvider(config=config)

    @staticmethod
    def _provider_is_applicable(provider_name: str, config: dict[str, Any]) -> bool:
        """Determine if a provider is applicable given the current environment and config."""
        if provider_name == "AssumeRoleWithWebIdentity":
            return bool(os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"))
        if provider_name == "StaticCredential":
            return bool(
                config.get("aws_access_key_id") and config.get("aws_secret_access_key")
            )
        if provider_name == "AssumeRole":
            return True  # Always valid fallback
        return False

    @classmethod
    def _detect_strategy_type(cls, config: dict[str, Any]) -> type[StrategyType]:
        """
        Detect the appropriate strategy type based on the global configuration.
        """

        if config["account_role_arn"]:
            return OrganizationsStrategy

        account_role_arns = config["account_role_arns"]
        if account_role_arns and len(account_role_arns) > 0:
            return MultiAccountStrategy

        return SingleAccountStrategy

    @classmethod
    async def create(cls) -> StrategyType:
        if cls._cached_strategy is not None:
            return cls._cached_strategy
        config = ocean.integration_config

        provider: CredentialProvider
        strategy_cls: type[StrategyType]

        provider = cls._detect_provider_type(config)
        strategy_cls = cls._detect_strategy_type(config)

        logger.info(f"Initializing {strategy_cls.__name__}")
        strategy = strategy_cls(provider=provider, config=config)
        logger.info(f"Successfully initialized {strategy_cls.__name__}")

        cls._cached_strategy = strategy
        return strategy


class AccountInfo(TypedDict):
    Id: str
    Name: str


async def get_all_account_sessions() -> AsyncIterator[tuple[AccountInfo, AioSession]]:
    strategy = await AccountStrategyFactory.create()
    async for account_info, session in strategy.get_account_sessions():
        yield AccountInfo(Id=account_info["Id"], Name=account_info["Name"]), session
