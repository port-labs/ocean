"""Tests for TemplateCache class"""

from typing import Dict, Any

from http_server.auth.custom.template_cache import TemplateCache


class TestTemplateCache:
    """Test TemplateCache"""

    def test_init_creates_empty_cache(self) -> None:
        """Test that TemplateCache initializes with empty cache"""
        cache = TemplateCache()

        assert cache._auth_response_hash is None
        assert cache._evaluated_headers is None
        assert cache._evaluated_query_params is None
        assert cache._evaluated_body is None

    def test_is_valid_returns_false_when_empty(self) -> None:
        """Test that is_valid returns False for empty cache"""
        cache = TemplateCache()

        assert cache.is_valid("some-hash") is False
        assert cache.is_valid(None) is False

    def test_is_valid_returns_false_for_different_hash(self) -> None:
        """Test that is_valid returns False for different hash"""
        cache = TemplateCache()
        cache.update("hash1", {"h": "v"}, {"q": "v"}, {"b": "v"})

        assert cache.is_valid("hash2") is False
        assert cache.is_valid("hash1") is True

    def test_get_cached_returns_empty_dicts_when_empty(self) -> None:
        """Test that get_cached returns empty dicts when cache is empty"""
        cache = TemplateCache()

        headers, query_params, body = cache.get_cached()

        assert headers == {}
        assert query_params == {}
        assert body == {}

    def test_update_stores_values(self) -> None:
        """Test that update stores the provided values"""
        cache = TemplateCache()
        headers: Dict[str, str] = {"Authorization": "Bearer token"}
        query_params: Dict[str, Any] = {"api_key": "key"}
        body: Dict[str, Any] = {"token": "value"}

        cache.update("hash123", headers, query_params, body)

        assert cache._auth_response_hash == "hash123"
        assert cache._evaluated_headers == headers
        assert cache._evaluated_query_params == query_params
        assert cache._evaluated_body == body

    def test_get_cached_returns_stored_values(self) -> None:
        """Test that get_cached returns the stored values"""
        cache = TemplateCache()
        headers: Dict[str, str] = {"Authorization": "Bearer token"}
        query_params: Dict[str, Any] = {"api_key": "key"}
        body: Dict[str, Any] = {"token": "value"}

        cache.update("hash123", headers, query_params, body)

        cached_headers, cached_query_params, cached_body = cache.get_cached()

        assert cached_headers == headers
        assert cached_query_params == query_params
        assert cached_body == body

    def test_invalidate_clears_cache(self) -> None:
        """Test that invalidate clears all cached values"""
        cache = TemplateCache()
        cache.update("hash123", {"h": "v"}, {"q": "v"}, {"b": "v"})

        cache.invalidate()

        assert cache._auth_response_hash is None
        assert cache._evaluated_headers is None
        assert cache._evaluated_query_params is None
        assert cache._evaluated_body is None
        assert cache.is_valid("hash123") is False

    def test_is_valid_returns_true_for_matching_hash(self) -> None:
        """Test that is_valid returns True when hash matches and cache is populated"""
        cache = TemplateCache()
        cache.update("hash123", {"h": "v"}, {"q": "v"}, {"b": "v"})

        assert cache.is_valid("hash123") is True

    def test_is_valid_returns_false_when_partial_cache(self) -> None:
        """Test that is_valid returns False when cache is partially populated"""
        cache = TemplateCache()
        # Manually set only some values (simulating partial state)
        cache._auth_response_hash = "hash123"
        cache._evaluated_headers = {"h": "v"}
        # query_params and body are None

        assert cache.is_valid("hash123") is False
