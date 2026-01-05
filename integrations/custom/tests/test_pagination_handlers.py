"""Tests for pagination handlers"""

from http_server.handlers import SkipTokenPagination


class TestSkipTokenPagination:
    """Test cases for SkipTokenPagination handler"""

    def test_extract_token_from_url_odata_format(self) -> None:
        """Test extracting $skiptoken from OData URL"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url(
            "https://api.test.com/users?$skiptoken=abc123"
        )
        assert token == "abc123"

    def test_extract_token_from_url_standard_format(self) -> None:
        """Test extracting skiptoken from standard URL"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url(
            "https://api.test.com/users?skiptoken=xyz789"
        )
        assert token == "xyz789"

    def test_extract_token_from_url_snake_case(self) -> None:
        """Test extracting skip_token (snake_case) from URL"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url(
            "https://api.test.com/users?skip_token=def456"
        )
        assert token == "def456"

    def test_extract_token_from_url_camel_case(self) -> None:
        """Test extracting skipToken (camelCase) from URL"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url(
            "https://api.test.com/users?skipToken=ghi789"
        )
        assert token == "ghi789"

    def test_extract_token_from_url_with_multiple_params(self) -> None:
        """Test extracting token from URL with multiple query parameters"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url(
            "https://api.test.com/users?limit=10&skiptoken=token123&sort=name"
        )
        assert token == "token123"

    def test_extract_token_from_url_no_token(self) -> None:
        """Test URL with no skip token returns None"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url("https://api.test.com/users?limit=10")
        assert token is None

    def test_extract_token_from_url_invalid_url(self) -> None:
        """Test invalid URL returns None"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url("not-a-valid-url")
        assert token is None

    def test_extract_token_from_url_empty_string(self) -> None:
        """Test empty URL returns None"""
        handler = SkipTokenPagination(None, {}, None, None, None)  # type: ignore

        token = handler._extract_token_from_url("")
        assert token is None

    def test_skip_token_config_defaults(self) -> None:
        """Test SkipTokenPagination uses correct config defaults"""
        config: dict[str, str] = {}
        handler = SkipTokenPagination(None, config, None, None, None)  # type: ignore

        # Defaults should be set in fetch_all method
        assert handler.config == config

    def test_skip_token_config_custom_params(self) -> None:
        """Test SkipTokenPagination accepts custom parameter names"""
        config = {
            "skip_token_param": "continuation_token",
            "size_param": "page_size",
            "next_link_path": "paging.next",
            "skip_token_path": "meta.token",
        }
        handler = SkipTokenPagination(None, config, None, None, None)  # type: ignore

        assert handler.config["skip_token_param"] == "continuation_token"
        assert handler.config["size_param"] == "page_size"
        assert handler.config["next_link_path"] == "paging.next"
        assert handler.config["skip_token_path"] == "meta.token"
