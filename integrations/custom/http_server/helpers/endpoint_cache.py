import hashlib
import json
from loguru import logger
from collections import Counter
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import aiofiles  # type: ignore[import-untyped]

from http_server.overrides import HttpServerResourceConfig, HttpServerSelector

CACHE_DIR = "/tmp/ocean/.endpoint_response_cache"


def _normalize_dict(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    return value


def make_cache_key(
    endpoint: str,
    method: str,
    query_params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> str:
    normalized = json.dumps(
        {
            "endpoint": endpoint,
            "method": (method or "GET").upper(),
            "query_params": _normalize_dict(query_params),
            "headers": _normalize_dict(headers),
            "body": _normalize_dict(body),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    safe_endpoint = endpoint.replace("/", "_").strip("_")[:60]
    return f"{safe_endpoint}_{digest}"


def analyze_cacheable_endpoints(
    resources: List[HttpServerResourceConfig],
) -> set[str]:
    """Scan all resource configs and return cache keys that appear 2+ times.

    Counts both direct kind endpoints and path_parameter discovery endpoints.
    """
    key_counts: Counter[str] = Counter()
    key_to_endpoint: Dict[str, str] = {}

    for resource in resources:
        selector: HttpServerSelector = resource.selector
        kind_key = make_cache_key(
            endpoint=resource.kind,
            method=selector.method,
            query_params=selector.query_params,
            headers=selector.headers,
            body=getattr(selector, "body", None),
        )
        key_counts[kind_key] += 1
        key_to_endpoint[kind_key] = f"{selector.method.upper()} {resource.kind}"

        path_parameters = selector.path_parameters or {}
        for param_config in path_parameters.values():
            param_key = make_cache_key(
                endpoint=param_config.endpoint,
                method=param_config.method,
                query_params=param_config.query_params,
                headers=param_config.headers,
            )
            key_counts[param_key] += 1
            key_to_endpoint[param_key] = (
                f"{param_config.method.upper()} {param_config.endpoint}"
            )

    cacheable = {key for key, count in key_counts.items() if count >= 2}

    for key, count in key_counts.items():
        endpoint_label = key_to_endpoint.get(key, key)
        if key in cacheable:
            logger.info(
                f"Caching enabled for '{endpoint_label}' — referenced {count} times across resource configs"
            )
        else:
            logger.info(
                f"Caching skipped for '{endpoint_label}' — only referenced {count} time"
            )

    logger.info(
        f"Endpoint cache analysis complete: {len(cacheable)} endpoint(s) will be cached, "
        f"{len(key_counts) - len(cacheable)} skipped, "
        f"{len(key_counts)} total"
    )
    return cacheable


class EndpointCache:
    """File-based streaming cache for raw API paginated responses."""

    def __init__(self, cacheable_keys: set[str], cache_dir: str = CACHE_DIR) -> None:
        self._cacheable_keys = cacheable_keys
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._clear_stale_files()

    def _clear_stale_files(self) -> None:
        """Remove leftover cache files from a previous resync (e.g. after a crash or Ctrl+C)."""
        stale = list(self._cache_dir.glob("*.ndjson"))
        if stale:
            for f in stale:
                try:
                    f.unlink()
                except OSError:
                    pass
            logger.info(f"Cleared {len(stale)} stale cache file(s) from a previous run")

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.ndjson"

    def is_cacheable(self, key: str) -> bool:
        return key in self._cacheable_keys

    def has_cached(self, key: str) -> bool:
        return self._cache_path(key).exists()

    async def write_through(
        self,
        key: str,
        source: AsyncGenerator[List[Dict[str, Any]], None],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Iterate *source*, persist each batch to an NDJSON file, and yield it."""
        path = self._cache_path(key)
        async with aiofiles.open(str(path), mode="w") as fh:
            async for batch in source:
                line = json.dumps(batch, separators=(",", ":"))
                await fh.write(line + "\n")
                yield batch

    async def read_stream(
        self,
        key: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Stream batches back from a previously written NDJSON cache file."""
        path = self._cache_path(key)
        async with aiofiles.open(str(path), mode="r") as fh:
            async for line in fh:
                stripped = line.strip()
                if stripped:
                    yield json.loads(stripped)

    async def get_or_fetch(
        self,
        endpoint: str,
        method: str,
        query_params: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        body: Optional[Dict[str, Any]],
        fetch_fn: Callable[[], AsyncGenerator[List[Dict[str, Any]], None]],
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Main API -- returns cached data when available, otherwise fetches and caches."""
        key = make_cache_key(endpoint, method, query_params, headers, body)

        if not self.is_cacheable(key):
            logger.info(f"Fetching '{method} {endpoint}' directly (not cached)")
            async for batch in fetch_fn():
                yield batch
            return

        if self.has_cached(key):
            logger.info(f"Serving '{method} {endpoint}' from cache")
            async for batch in self.read_stream(key):
                yield batch
            return

        logger.info(
            f"Cache miss for '{method} {endpoint}', fetching and caching response"
        )
        async for batch in self.write_through(key, fetch_fn()):
            yield batch
        logger.info(f"Cached response for '{method} {endpoint}' written to disk")

    def clear(self) -> None:
        """Remove all NDJSON cache files."""
        removed = 0
        for cache_file in self._cache_dir.glob("*.ndjson"):
            try:
                cache_file.unlink()
                removed += 1
            except OSError:
                pass
        if removed:
            logger.info(f"Removed {removed} cached response file(s)")


_cache: Optional[EndpointCache] = None


def initialize_endpoint_cache(
    resources: List[HttpServerResourceConfig],
) -> EndpointCache:
    global _cache
    cacheable = analyze_cacheable_endpoints(resources)
    _cache = EndpointCache(cacheable_keys=cacheable)
    logger.info(
        f"Endpoint cache initialized with {len(cacheable)} cacheable endpoint(s)"
    )
    return _cache


def get_endpoint_cache() -> Optional[EndpointCache]:
    return _cache


def clear_endpoint_cache() -> None:
    global _cache
    if _cache is not None:
        _cache.clear()
        _cache = None
        logger.info("Endpoint cache cleared")
