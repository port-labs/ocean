"""Manages caching of evaluated templates to avoid re-evaluation on every request."""

from typing import Dict, Any, Optional


class TemplateCache:
    """Manages caching of evaluated templates to avoid re-evaluation on every request."""

    def __init__(self) -> None:
        self._auth_response_hash: Optional[str] = None
        self._evaluated_headers: Optional[Dict[str, str]] = None
        self._evaluated_query_params: Optional[Dict[str, Any]] = None
        self._evaluated_body: Optional[Dict[str, Any]] = None

    def invalidate(self) -> None:
        """Invalidate the cache when auth_response changes."""
        self._auth_response_hash = None
        self._evaluated_headers = None
        self._evaluated_query_params = None
        self._evaluated_body = None

    def is_valid(self, current_hash: Optional[str]) -> bool:
        """Check if cache is valid for the given hash."""
        return (
            current_hash is not None
            and self._auth_response_hash == current_hash
            and self._evaluated_headers is not None
            and self._evaluated_query_params is not None
            and self._evaluated_body is not None
        )

    def get_cached(self) -> tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
        """Get cached evaluated templates."""
        return (
            self._evaluated_headers or {},
            self._evaluated_query_params or {},
            self._evaluated_body or {},
        )

    def update(
        self,
        hash_value: Optional[str],
        headers: Dict[str, str],
        query_params: Dict[str, Any],
        body: Dict[str, Any],
    ) -> None:
        """Update cache with new evaluated templates."""
        self._auth_response_hash = hash_value
        self._evaluated_headers = headers
        self._evaluated_query_params = query_params
        self._evaluated_body = body
