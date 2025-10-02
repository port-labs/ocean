from azure.models import ResourceGroupTagFilters
from azure.utils import build_rg_tag_filter_clause


class TestResourceContainersFiltering:
    """Test the resource containers filtering functionality."""

    def test_build_rg_tag_filter_clause_empty_filters(self) -> None:
        """Test building filter clause with empty filters."""
        filters = ResourceGroupTagFilters()
        result = build_rg_tag_filter_clause(filters)
        assert result == ""

    def test_build_rg_tag_filter_clause_include_only(self) -> None:
        """Test building filter clause with include filters only."""
        filters = ResourceGroupTagFilters(included={"Environment": "Production"})
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert "tostring(tags['Environment']) =~ 'Production'" in result

    def test_build_rg_tag_filter_clause_exclude_only(self) -> None:
        """Test building filter clause with exclude filters only."""
        filters = ResourceGroupTagFilters(excluded={"Temporary": "true"})
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert "not (" in result
        assert "tostring(tags['Temporary']) =~ 'true'" in result

    def test_build_rg_tag_filter_clause_both_include_and_exclude(self) -> None:
        """Test building filter clause with both include and exclude filters."""
        filters = ResourceGroupTagFilters(
            included={"Environment": "Production"}, excluded={"Temporary": "true"}
        )
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert " and " in result
        assert "not (" in result

    def test_build_rg_tag_filter_clause_escapes_quotes(self) -> None:
        """Test that quotes in tag values are properly escaped."""
        filters = ResourceGroupTagFilters(included={"Name": "O'Connor"})
        result = build_rg_tag_filter_clause(filters)
        assert "O''Connor" in result  # Single quote should be doubled
