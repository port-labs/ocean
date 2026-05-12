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
                logger.warning(f"Unknown provider '{provider_name}', skipping...")
                continue

            if cls._provider_is_applicable(provider_name, config):
                logger.info(
                    f"Using {provider_cls.__name__} (priority: {provider_name})"
                )
                return provider_cls(config=config)

            logger.debug(
                f"Provider '{provider_name}' failed to satisfy config requirement, skipping..."
            )

        logger.warning("No valid provider found; falling back to assuming role")
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
            return bool(
                config.get("account_role_arn") or config.get("account_role_arns")
            )
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
        """Create or get the cached strategy instance."""
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


async def initialize_aws_account_sessions() -> None:
    """Validate and initialize all AWS account sessions"""
    logger.info("Initializing AWS account sessions")
    strategy = await AccountStrategyFactory.create()
    await strategy.healthcheck()
    logger.info("AWS account sessions initialized successfully")


async def get_all_account_sessions() -> AsyncIterator[tuple[AccountInfo, AioSession]]:
    strategy = await AccountStrategyFactory.create()
    async for account_info, session in strategy.get_account_sessions():
        yield AccountInfo(Id=account_info["Id"], Name=account_info["Name"]), session


async def clear_aws_account_sessions() -> None:
    """Clear AWS account sessions after resync completes by deleting the cached strategy."""
    if AccountStrategyFactory._cached_strategy:
        AccountStrategyFactory._cached_strategy = None
        logger.debug("All cached AWS account sessions have been cleared.")


async def get_session_for_account(account_id: str) -> AioSession | None:
    """Return a cached session for ``account_id`` used by webhook handlers.

    Reuses ``AccountStrategyFactory.create()`` (never calls
    ``clear_aws_account_sessions``). Builds a lazy ``account_id -> session``
    map on the strategy instance; multi/org strategies key sessions by role
    ARN, so ARN is reversed via ``extract_account_from_arn``.

    For multi-account and organizations strategies, if role sessions are not
    populated yet (e.g. no resync has run), this runs ``healthcheck()`` once—
    matching the guard in ``get_account_sessions()``—then builds the map.
    """

    strategy = await AccountStrategyFactory.create()

    # Cache is attached to the cached strategy instance so it is invalidated
    # automatically when `clear_aws_account_sessions()` resets the strategy.
    cached = getattr(strategy, "_account_id_to_session", None)
    if isinstance(cached, dict) and account_id in cached:
        session = cached.get(account_id)
        return session if isinstance(session, AioSession) else None

    account_id_to_session: dict[str, AioSession] = {}

    # Single account strategy exposes `account_id` + `_session` after healthcheck.
    if isinstance(strategy, SingleAccountStrategy):
        if strategy._session is None or strategy.account_id is None:
            await strategy.healthcheck()
        if strategy._session is not None and strategy.account_id is not None:
            account_id_to_session[strategy.account_id] = strategy._session

        setattr(strategy, "_account_id_to_session", account_id_to_session)
        return account_id_to_session.get(account_id)

    # Multi-account / organizations store sessions keyed by role ARN.
    from aws.auth.utils import extract_account_from_arn

    role_arn_to_session = getattr(strategy, "valid_sessions", None)
    if role_arn_to_session is None:
        role_arn_to_session = getattr(strategy, "_valid_sessions", None)
    if not isinstance(role_arn_to_session, dict):
        setattr(strategy, "_account_id_to_session", account_id_to_session)
        return None

    # Webhooks may run before any resync. `get_account_sessions()` runs
    # `healthcheck()` when caches are empty; mirror that here so
    # `valid_sessions` is populated before we build the account_id map.
    if not role_arn_to_session:
        await strategy.healthcheck()
        strategy.__dict__.pop("_account_id_to_session", None)
        role_arn_to_session = getattr(strategy, "valid_sessions", None)
        if role_arn_to_session is None:
            role_arn_to_session = getattr(strategy, "_valid_sessions", None)
        if not isinstance(role_arn_to_session, dict):
            setattr(strategy, "_account_id_to_session", account_id_to_session)
            return None

    for role_arn, session in role_arn_to_session.items():
        if not isinstance(role_arn, str) or not isinstance(session, AioSession):
            continue
        try:
            role_account_id = extract_account_from_arn(role_arn)
        except Exception:
            continue
        account_id_to_session[role_account_id] = session

    setattr(strategy, "_account_id_to_session", account_id_to_session)
    return account_id_to_session.get(account_id)
