import pickle
from pathlib import Path
from typing import Any, Optional

from port_ocean.cache.base import CacheProvider
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.core.models import CachingStorageMode


class FailedToReadCacheFileError(FailedToReadCacheError):
    pass


class FailedToWriteCacheFileError(FailedToWriteCacheError):
    pass


class DiskCacheProvider(CacheProvider):
    STORAGE_TYPE = CachingStorageMode.disk

    def __init__(self, cache_dir: str | None = None) -> None:
        if cache_dir is None:
            cache_dir = ".ocean_cache"
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.pkl"

    async def get(self, key: str) -> Optional[Any]:
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except (pickle.PickleError, EOFError) as e:
            raise FailedToReadCacheFileError(
                f"Failed to read cache file: {cache_path}: {str(e)}"
            )

    async def set(self, key: str, value: Any) -> None:
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(value, f)
        except (pickle.PickleError, IOError) as e:
            raise FailedToWriteCacheFileError(
                f"Failed to write cache file: {cache_path}: {str(e)}"
            )

    async def clear(self) -> None:
        try:
            for cache_file in self._cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                except OSError:
                    pass
        except OSError:
            pass
