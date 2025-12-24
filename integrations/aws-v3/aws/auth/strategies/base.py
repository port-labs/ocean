from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from loguru import logger


class AWSSessionStrategy(ABC):
    """Base class for AWS session strategies."""

    def __init__(self, provider: CredentialProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    @abstractmethod
    def get_account_sessions(
        self,
    ) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
        """Yield (AccountInfo, AioSession) pairs for each account managed by this strategy."""
        pass


class HealthCheckMixin(ABC):
    @abstractmethod
    async def healthcheck(self) -> bool:
        pass


class CachedHealthCheckMixin(HealthCheckMixin):
    """
    Mixin that provides shared cache functionality for healthcheck results.
    Uses cache_coroutine_result decorator for automatic caching.
    Strategies implement the abstract methods to customize cache behavior.
    """

    @abstractmethod
    async def _get_healthcheck_data(
        self,
        role_arn: str,
        external_id: str | None,
        region: str | None,
    ) -> dict[str, Any]:
        """
        Get healthcheck data. This method should be decorated with @cache_coroutine_result.
        The decorator will automatically cache the return value based on function signature and arguments.
        Returns dict with cacheable data (valid_arns, discovered_accounts, etc.).
        """
        pass

    @abstractmethod
    async def _restore_from_cache_data(self, cache_data: dict[str, Any]) -> bool:
        """
        Restore strategy state from cached data.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def _get_cache_key_params(self) -> dict[str, str | None]:
        """
        Get parameters that should be used for cache key generation.
        Returns dict with role_arn, external_id, region.
        These will be passed as kwargs to _get_healthcheck_data().
        """
        pass
