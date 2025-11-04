from typing import Any, Optional

from port_ocean.cache.base import CacheProvider
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.core.models import CachingStorageMode
import time
import pickle
import os
from collections import OrderedDict
from loguru import logger


class FailedToReadHybridCacheError(FailedToReadCacheError):
    pass


class FailedToWriteHybridCacheError(FailedToWriteCacheError):
    pass


DEFAULT_CACHE_FILE = "/tmp/ocean/.ocean_cache/smart_cache.pkl"
DEFAULT_CACHE_TTL = 3600
DEFAULT_CACHE_MAX_SIZE = 100


class HybridCacheProvider(CacheProvider):
    STORAGE_TYPE = CachingStorageMode.hybrid

    def __init__(
        self,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
        default_ttl: int = DEFAULT_CACHE_TTL,
        cache_file: str = DEFAULT_CACHE_FILE,
    ) -> None:
        """
        Initialize the cache with optional disk persistence.
        - max_size: Maximum number of entries before eviction (LRU).
        - default_ttl: Default time-to-live in seconds (None means no expiration).
        - cache_file: Path to pickle file for disk fallback (None disables persistence).
        - cache: An ordered dictionary to store the cache (default is an empty OrderedDict).
        """
        self.cache: OrderedDict[str, tuple[Any, float, Optional[int]]] = OrderedDict()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache_file = cache_file
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load cache from pickle file if it exists and is valid."""
        if not self.cache_file or not os.path.exists(self.cache_file):
            return

        try:
            with open(self.cache_file, "rb") as f:
                disk_cache = pickle.load(f)
            if isinstance(disk_cache, OrderedDict):
                current_time = time.time()
                records_to_remove = []
                for key, (_, timestamp, ttl) in disk_cache.items():
                    if ttl is not None and timestamp + ttl < current_time:
                        records_to_remove.append(key)
                for key in records_to_remove:
                    del disk_cache[key]
                self.cache = disk_cache
                logger.debug(
                    f"Loaded {len(self.cache)} records from disk cache: {self.cache_file}"
                )
            else:
                logger.warning(
                    "Invalid cache file format. Expected OrderedDict, got %s",
                    type(disk_cache),
                )
        except (pickle.UnpicklingError, EOFError, OSError) as e:
            logger.warning(
                f"Failed to load cache from disk: {e}. Starting with empty cache."
            )
            raise FailedToReadHybridCacheError(
                f"Failed to load cache from disk: {e}. Starting with empty cache."
            )
        except Exception as e:
            logger.warning(f"Unexpected error loading cache: {e}. Starting fresh.")
            raise FailedToReadHybridCacheError(
                f"Unexpected error loading cache: {e}. Starting fresh."
            )

    def _save_to_disk(self) -> None:
        """Save cache to pickle file."""
        if not self.cache_file:
            return
        try:
            # writing to a temp file first for atomicity
            temp_file = self.cache_file + ".tmp"
            with open(temp_file, "wb") as f:
                pickle.dump(self.cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(temp_file, self.cache_file)
            logger.debug(
                f"Saved {len(self.cache)} records to disk cache: {self.cache_file}"
            )
        except (pickle.PicklingError, IOError) as e:
            logger.warning(
                f"Failed to save cache to disk: {e}. Cache will not be persisted."
            )
            raise FailedToWriteHybridCacheError(
                f"Failed to save cache to disk: {e}. Cache will not be persisted."
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error saving cache: {e}. Cache will not be persisted."
            )
            raise FailedToWriteHybridCacheError(
                f"Unexpected error saving cache: {e}. Cache will not be persisted."
            )

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value if exists and not expired, else None. Move to end for LRU."""
        if key not in self.cache:
            return None
        value, timestamp, ttl = self.cache[key]
        if ttl is not None and timestamp + ttl < time.time():
            del self.cache[key]
            self._save_to_disk()
            return None
        self.cache.move_to_end(key)
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL. Evict least recently used if cache exceeds max_size."""
        timestamp = time.time()
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = (value, timestamp, ttl)
        self.cache.move_to_end(key)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
        self._save_to_disk()

    async def clear(self) -> None:
        """Clear the entire cache."""
        self.cache.clear()
        self._save_to_disk()
