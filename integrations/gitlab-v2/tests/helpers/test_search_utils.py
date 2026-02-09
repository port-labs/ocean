"""Tests for the search utility functions."""
import pytest

from gitlab.entity_processors.utils import parse_search_string


class TestParseSearchString:
    """Tests for the parse_search_string utility function."""

    def test_parse_valid_search_string(self) -> None:
        """Test parsing a valid search string with scope and query."""
        scope, query = parse_search_string("scope=blobs&&query=filename:port.yml")
        assert scope == "blobs"
        assert query == "filename:port.yml"

    def test_parse_search_string_with_commits_scope(self) -> None:
        """Test parsing a search string with commits scope."""
        scope, query = parse_search_string("scope=commits&&query=fix bug")
        assert scope == "commits"
        assert query == "fix bug"

    def test_parse_search_string_with_equals_in_query(self) -> None:
        """Test parsing a search string where query contains '=' characters."""
        scope, query = parse_search_string("scope=blobs&&query=key=value")
        assert scope == "blobs"
        assert query == "key=value"

    def test_parse_search_string_with_spaces(self) -> None:
        """Test parsing a search string with spaces around parts."""
        scope, query = parse_search_string("scope=blobs && query=filename:test.yml")
        assert scope == "blobs"
        assert query == "filename:test.yml"

    def test_parse_search_string_missing_separator(self) -> None:
        """Test that missing && separator raises ValueError."""
        with pytest.raises(ValueError, match="scope=.*query="):
            parse_search_string("scope=blobs query=test")

    def test_parse_search_string_missing_scope(self) -> None:
        """Test that missing scope= raises ValueError."""
        with pytest.raises(ValueError):
            parse_search_string("blobs&&query=test")

    def test_parse_search_string_missing_query(self) -> None:
        """Test that missing query= raises ValueError."""
        with pytest.raises(ValueError):
            parse_search_string("scope=blobs&&test")

    def test_parse_search_string_empty_string(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_search_string("")

    def test_parse_search_string_wiki_blobs_scope(self) -> None:
        """Test parsing with wiki_blobs scope."""
        scope, query = parse_search_string("scope=wiki_blobs&&query=README")
        assert scope == "wiki_blobs"
        assert query == "README"
