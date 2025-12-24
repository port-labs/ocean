from aws.auth.providers.base import CredentialProvider
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
import hashlib
import base64


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
    Strategies implement the abstract methods to customize cache behavior.
    """

    @abstractmethod
    def _get_cache_key(self) -> str:
        """Generate unique cache key for this strategy's configuration."""
        pass

    @abstractmethod
    async def _extract_cache_data(self) -> dict[str, Any]:
        """Extract data to cache after successful healthcheck."""
        pass

    @abstractmethod
    async def _restore_from_cache_data(self, cache_data: dict[str, Any]) -> bool:
        """Restore strategy state from cached data. Returns True if successful."""
        pass

    def _sanitize_cache_key(self, key: str) -> str:
        """
        Sanitize cache key to be filesystem-safe by hashing it.
        Returns a short hash that's safe for use as a filename.
        """
        # Create a hash of the key to make it filesystem-safe
        digest = hashlib.sha256(key.encode()).digest()[:8]
        short_hash = base64.urlsafe_b64encode(digest).decode("ascii")
        short_hash = short_hash.rstrip("=").replace("-", "_").replace("+", "_")
        
        # Prefix with strategy name for readability
        strategy_name = self.__class__.__name__.lower().replace("strategy", "").replace("healthcheckmixin", "")
        return f"{strategy_name}_healthcheck_{short_hash}"

    async def _try_load_from_cache(self) -> bool:
        """Try to load healthcheck results from shared cache."""
        try:
            cache_key = self._get_cache_key()
            sanitized_key = self._sanitize_cache_key(cache_key)
            cached_data = await ocean.app.cache_provider.get(sanitized_key)

            if not cached_data:
                return False

            logger.info(
                f"Loading healthcheck results from cache: {cache_key[:50]}..."
            )
            return await self._restore_from_cache_data(cached_data)

        except FailedToReadCacheError as e:
            logger.debug(f"Cache miss for {self.__class__.__name__}: {e}")
            return False
        except Exception as e:
            logger.warning(
                f"Error loading cache for {self.__class__.__name__}: {e}, "
                "running healthcheck"
            )
            return False

    async def _save_to_cache(self) -> None:
        """Save healthcheck results to shared cache."""
        try:
            cache_key = self._get_cache_key()
            sanitized_key = self._sanitize_cache_key(cache_key)
            cache_data = await self._extract_cache_data()
            await ocean.app.cache_provider.set(sanitized_key, cache_data)
            logger.debug(f"Cached healthcheck results: {cache_key[:50]}...")
        except FailedToWriteCacheError as e:
            logger.warning(f"Failed to write cache for {self.__class__.__name__}: {e}")
        except Exception as e:
            logger.warning(
                f"Error writing cache for {self.__class__.__name__}: {e}"
            )
