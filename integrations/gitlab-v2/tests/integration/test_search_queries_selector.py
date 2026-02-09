"""Tests for SearchQuery model and ProjectSelector.search_queries field."""
import pytest
from pydantic import ValidationError

from integration import SearchQuery, ProjectSelector


class TestSearchQueryModel:
    """Tests for the SearchQuery Pydantic model."""

    def test_search_query_with_all_fields(self) -> None:
        """Test creating a SearchQuery with all fields."""
        sq = SearchQuery(name="hasPortYml", scope="blobs", query="filename:port.yml")
        assert sq.name == "hasPortYml"
        assert sq.scope == "blobs"
        assert sq.query == "filename:port.yml"

    def test_search_query_default_scope(self) -> None:
        """Test that SearchQuery defaults scope to 'blobs'."""
        sq = SearchQuery(name="testQuery", query="test")
        assert sq.scope == "blobs"

    def test_search_query_custom_scope(self) -> None:
        """Test creating a SearchQuery with a custom scope."""
        sq = SearchQuery(name="commitSearch", scope="commits", query="fix bug")
        assert sq.scope == "commits"

    def test_search_query_missing_name(self) -> None:
        """Test that SearchQuery requires 'name'."""
        with pytest.raises(ValidationError):
            SearchQuery(query="test")  # type: ignore

    def test_search_query_missing_query(self) -> None:
        """Test that SearchQuery requires 'query'."""
        with pytest.raises(ValidationError):
            SearchQuery(name="test")  # type: ignore

    def test_search_query_dict_output(self) -> None:
        """Test dict serialization of SearchQuery."""
        sq = SearchQuery(name="hasCI", scope="blobs", query="filename:.gitlab-ci.yml")
        d = sq.dict()
        assert d["name"] == "hasCI"
        assert d["scope"] == "blobs"
        assert d["query"] == "filename:.gitlab-ci.yml"


class TestProjectSelectorSearchQueries:
    """Tests for the search_queries field on ProjectSelector."""

    def test_selector_default_empty_search_queries(self) -> None:
        """Test that ProjectSelector has an empty search_queries list by default."""
        selector = ProjectSelector(query="true")
        assert selector.search_queries == []

    def test_selector_with_search_queries(self) -> None:
        """Test ProjectSelector with search queries provided."""
        selector = ProjectSelector(
            query="true",
            searchQueries=[  # type: ignore[call-arg]
                {"name": "hasPortYml", "scope": "blobs", "query": "filename:port.yml"},
                {"name": "hasDocker", "query": "filename:Dockerfile"},
            ],
        )
        assert len(selector.search_queries) == 2
        assert selector.search_queries[0].name == "hasPortYml"
        assert selector.search_queries[0].scope == "blobs"
        assert selector.search_queries[0].query == "filename:port.yml"
        assert selector.search_queries[1].name == "hasDocker"
        assert selector.search_queries[1].scope == "blobs"  # default
        assert selector.search_queries[1].query == "filename:Dockerfile"

    def test_selector_with_empty_search_queries_list(self) -> None:
        """Test ProjectSelector with explicitly empty search queries."""
        selector = ProjectSelector(query="true", searchQueries=[])  # type: ignore[call-arg]
        assert selector.search_queries == []

    def test_selector_search_queries_alias(self) -> None:
        """Test that 'searchQueries' alias works for 'search_queries'."""
        selector = ProjectSelector(
            query="true",
            searchQueries=[  # type: ignore[call-arg]
                {"name": "test", "query": "test_query"}
            ],
        )
        # The Python attribute name is search_queries
        assert len(selector.search_queries) == 1
        assert selector.search_queries[0].name == "test"

    def test_selector_invalid_search_query_entry(self) -> None:
        """Test that invalid search query entries raise ValidationError."""
        with pytest.raises(ValidationError):
            ProjectSelector(
                query="true",
                searchQueries=[  # type: ignore[call-arg]
                    {"scope": "blobs"}  # missing name and query
                ],
            )

    def test_selector_combined_fields(self) -> None:
        """Test ProjectSelector with multiple fields including search_queries."""
        selector = ProjectSelector(
            query="true",
            includeLanguages=True,  # type: ignore[call-arg]
            searchQueries=[  # type: ignore[call-arg]
                {"name": "hasCI", "scope": "blobs", "query": "filename:.gitlab-ci.yml"}
            ],
        )
        assert selector.include_languages is True
        assert len(selector.search_queries) == 1
        assert selector.search_queries[0].name == "hasCI"
