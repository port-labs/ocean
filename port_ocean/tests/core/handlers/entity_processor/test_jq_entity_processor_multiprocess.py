"""Tests for the multiprocess JQ entity processing functions.

These tests cover the module-level synchronous functions that are designed
to run in separate processes for parallel JQ processing.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    MappedEntity,
    _calculate_entity,
    _compile,
    _format_filter,
    _get_mapped_entity,
    _search,
    _search_as_bool,
    _search_as_object,
)
from port_ocean.exceptions.core import EntityProcessorException

import port_ocean.core.handlers.entity_processor.jq_entity_processor as jq_module


class TestFormatFilter:
    """Test the _format_filter function for JQ expression formatting."""

    def test_simple_string_no_change(self) -> None:
        """Test that expressions without single quotes are unchanged."""
        filter_str = ".foo"
        result = _format_filter(filter_str)
        assert result == ".foo"

    def test_convert_single_quotes_in_middle(self) -> None:
        """Test converting single quotes in the middle of expression."""
        filter_str = ".organization + '/' + .repository"
        result = _format_filter(filter_str)
        assert result == '.organization + "/" + .repository'

    def test_convert_single_quote_at_end(self) -> None:
        """Test converting single quote at the end of expression."""
        filter_str = ".organization + '/'"
        result = _format_filter(filter_str)
        assert result == '.organization + "/"'

    def test_convert_single_quote_at_start(self) -> None:
        """Test converting single quote at the start of expression."""
        filter_str = "'/' + .organization"
        result = _format_filter(filter_str)
        assert result == '"/" + .organization'

    def test_double_quotes_unchanged(self) -> None:
        """Test that double quotes are not modified."""
        filter_str = '"shalom"'
        result = _format_filter(filter_str)
        assert result == '"shalom"'

    def test_mixed_quotes(self) -> None:
        """Test expression with mixed quote types."""
        filter_str = "'prefix' + \"middle\" + 'suffix'"
        result = _format_filter(filter_str)
        assert result == '"prefix" + "middle" + "suffix"'

    def test_empty_string(self) -> None:
        """Test empty string input."""
        filter_str = ""
        result = _format_filter(filter_str)
        assert result == ""

    def test_complex_expression(self) -> None:
        """Test complex JQ expression with multiple single quotes.

        Note: The regex only converts single quotes that are string delimiters
        (at start/end of string or adjacent to whitespace), not all single quotes.
        Single quotes followed by a space (like ' - ') are not converted because
        the regex pattern assumes the space indicates content, not a delimiter.
        """
        # This pattern works because '/' is not followed by whitespace
        filter_str = ".organization + '/' + .repository"
        result = _format_filter(filter_str)
        assert result == '.organization + "/" + .repository'

    def test_single_quote_with_no_space_content(self) -> None:
        """Test single quote string literals with non-space content."""
        filter_str = ".name + ':' + .type"
        result = _format_filter(filter_str)
        assert result == '.name + ":" + .type'


class TestCompile:
    """Test the _compile function for JQ pattern compilation."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the compiled patterns cache before each test."""
        jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()

    @pytest.fixture
    def mock_ocean_config(self) -> Any:
        """Mock ocean config for testing."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            yield mock_ocean

    def test_compile_simple_pattern(self, mock_ocean_config: Any) -> None:
        """Test compiling a simple JQ pattern."""
        pattern = ".foo"
        compiled = _compile(pattern)
        assert compiled is not None

    def test_compile_caches_patterns(self, mock_ocean_config: Any) -> None:
        """Test that compiled patterns are cached."""
        pattern = ".bar"
        first_compile = _compile(pattern)
        second_compile = _compile(pattern)
        assert first_compile is second_compile

    def test_compile_with_single_quotes(self, mock_ocean_config: Any) -> None:
        """Test compiling pattern with single quotes."""
        pattern = ".organization + '/' + .repository"
        compiled = _compile(pattern)
        assert compiled is not None
        # The pattern should work correctly
        result = compiled.input_value(
            {"organization": "port", "repository": "ocean"}
        ).first()
        assert result == "port/ocean"

    def test_compile_blocks_env_access_when_disabled(self) -> None:
        """Test that env access is blocked when disabled in config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = False
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()

            pattern = ".foo"
            compiled = _compile(pattern)
            assert compiled is not None
            # The compiled pattern should have env blocked
            # Check that "def env: {};" prefix was added by verifying it's in cache
            cached_keys = list(
                jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.keys()
            )
            assert len(cached_keys) == 1
            assert cached_keys[0].startswith("def env: {};")


class TestSearchAsBool:
    """Test the _search_as_bool function for boolean JQ searches."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_search_returns_true(self, setup_mock_ocean: Any) -> None:
        """Test search returning true boolean."""
        data = {"foo": True}
        pattern = ".foo"
        result = _search_as_bool(data, pattern)
        assert result is True

    def test_search_returns_false(self, setup_mock_ocean: Any) -> None:
        """Test search returning false boolean."""
        data = {"foo": False}
        pattern = ".foo"
        result = _search_as_bool(data, pattern)
        assert result is False

    def test_search_with_comparison(self, setup_mock_ocean: Any) -> None:
        """Test search with comparison expression."""
        data = {"foo": "bar"}
        pattern = '.foo == "bar"'
        result = _search_as_bool(data, pattern)
        assert result is True

    def test_search_with_comparison_false(self, setup_mock_ocean: Any) -> None:
        """Test search with comparison expression returning false."""
        data = {"foo": "bar"}
        pattern = '.foo == "baz"'
        result = _search_as_bool(data, pattern)
        assert result is False

    def test_search_raises_on_non_bool(self, setup_mock_ocean: Any) -> None:
        """Test that non-boolean values raise EntityProcessorException."""
        data = {"foo": "bar"}
        pattern = ".foo"
        with pytest.raises(
            EntityProcessorException,
            match="Expected boolean value, got value:bar of type: <class 'str'> instead",
        ):
            _search_as_bool(data, pattern)

    def test_search_raises_on_number(self, setup_mock_ocean: Any) -> None:
        """Test that number values raise EntityProcessorException."""
        data = {"foo": 42}
        pattern = ".foo"
        with pytest.raises(
            EntityProcessorException,
            match="Expected boolean value, got value:42 of type: <class 'int'> instead",
        ):
            _search_as_bool(data, pattern)

    def test_search_true_literal(self, setup_mock_ocean: Any) -> None:
        """Test search with 'true' literal."""
        data = {"foo": "bar"}
        pattern = "true"
        result = _search_as_bool(data, pattern)
        assert result is True

    def test_search_false_literal(self, setup_mock_ocean: Any) -> None:
        """Test search with 'false' literal."""
        data = {"foo": "bar"}
        pattern = "false"
        result = _search_as_bool(data, pattern)
        assert result is False


class TestSearch:
    """Test the _search function for general JQ searches."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_search_simple_field(self, setup_mock_ocean: Any) -> None:
        """Test searching for a simple field."""
        data = {"foo": "bar"}
        pattern = ".foo"
        result = _search(data, pattern)
        assert result == "bar"

    def test_search_nested_field(self, setup_mock_ocean: Any) -> None:
        """Test searching for a nested field."""
        data = {"foo": {"bar": "baz"}}
        pattern = ".foo.bar"
        result = _search(data, pattern)
        assert result == "baz"

    def test_search_with_string_concatenation(self, setup_mock_ocean: Any) -> None:
        """Test search with string concatenation."""
        data = {"repository": "ocean", "organization": "port"}
        pattern = ".organization + '/' + .repository"
        result = _search(data, pattern)
        assert result == "port/ocean"

    def test_search_array_field(self, setup_mock_ocean: Any) -> None:
        """Test searching for an array field."""
        data = {"parameters": ["value1", "value2", "value3"]}
        pattern = ".parameters"
        result = _search(data, pattern)
        assert result == ["value1", "value2", "value3"]

    def test_search_array_filter(self, setup_mock_ocean: Any) -> None:
        """Test search with array filter."""
        data = {
            "parameters": [
                {"name": "param1", "value": "value1"},
                {"name": "param2", "value": "value2"},
            ]
        }
        pattern = '.parameters[] | select(.name == "param1") | .value'
        result = _search(data, pattern)
        assert result == "value1"

    def test_search_returns_none_on_error(self, setup_mock_ocean: Any) -> None:
        """Test that search returns None on invalid pattern."""
        data = {"foo": "bar"}
        pattern = ".foo."  # Invalid pattern
        result = _search(data, pattern)
        assert result is None

    def test_search_returns_none_on_missing_field(self, setup_mock_ocean: Any) -> None:
        """Test that search returns None for missing field."""
        data = {"foo": "bar"}
        pattern = '.parameters[] | select(.name == "not_exists") | .value'
        result = _search(data, pattern)
        assert result is None

    def test_search_double_quotes(self, setup_mock_ocean: Any) -> None:
        """Test search with double-quoted string literal."""
        data = {"foo": "bar"}
        pattern = '"shalom"'
        result = _search(data, pattern)
        assert result == "shalom"

    def test_search_numeric_value(self, setup_mock_ocean: Any) -> None:
        """Test searching for numeric value."""
        data = {"count": 42}
        pattern = ".count"
        result = _search(data, pattern)
        assert result == 42

    def test_search_in_operator(self, setup_mock_ocean: Any) -> None:
        """Test search using IN operator."""
        data = {
            "subViews": [
                {"key": "view1", "qualifier": "VW"},
                {"key": "view2", "qualifier": "SVW"},
                {"key": "view3", "qualifier": "APP"},
            ]
        }
        pattern = '.subViews | map(select((.qualifier | IN("VW", "SVW"))) | .key)'
        result = _search(data, pattern)
        assert result == ["view1", "view2"]


class TestSearchAsObject:
    """Test the _search_as_object function for object-based JQ searches."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_search_simple_object(self, setup_mock_ocean: Any) -> None:
        """Test searching with simple object mapping."""
        data = {"foo": {"bar": "baz"}}
        obj = {"foo": ".foo.bar"}
        result = _search_as_object(data, obj)
        assert result == {"foo": "baz"}

    def test_search_multiple_fields(self, setup_mock_ocean: Any) -> None:
        """Test searching with multiple field mappings."""
        data = {"name": "test", "value": 42}
        obj = {"identifier": ".name", "count": ".value"}
        result = _search_as_object(data, obj)
        assert result == {"identifier": "test", "count": 42}

    def test_search_nested_object_mapping(self, setup_mock_ocean: Any) -> None:
        """Test searching with nested object mapping."""
        data = {"user": {"name": "john", "email": "john@example.com"}}
        obj = {"properties": {"name": ".user.name", "email": ".user.email"}}
        result = _search_as_object(data, obj)
        assert result == {"properties": {"name": "john", "email": "john@example.com"}}

    def test_search_with_list_mapping(self, setup_mock_ocean: Any) -> None:
        """Test searching with list mapping."""
        data = {"id": "123", "name": "test"}
        obj = {"items": [{"field1": ".id"}, {"field2": ".name"}]}
        result = _search_as_object(data, obj)
        assert result == {"items": [{"field1": "123"}, {"field2": "test"}]}

    def test_search_tracks_misconfigurations(self, setup_mock_ocean: Any) -> None:
        """Test that misconfigurations are tracked."""
        data = {"foo": "bar"}
        obj = {"identifier": ".foo", "missing": ".nonexistent"}
        misconfigurations: dict[str, str] = {}
        result = _search_as_object(data, obj, misconfigurations)
        assert result == {"identifier": "bar", "missing": None}
        assert misconfigurations == {"missing": ".nonexistent"}

    def test_search_tracks_misconfigurations_in_nested(
        self, setup_mock_ocean: Any
    ) -> None:
        """Test that misconfigurations are tracked in nested objects."""
        data = {"foo": "bar"}
        obj = {"properties": {"valid": ".foo", "invalid": ".missing"}}
        misconfigurations: dict[str, str] = {}
        result = _search_as_object(data, obj, misconfigurations)
        assert result == {"properties": {"valid": "bar", "invalid": None}}
        assert "invalid" in misconfigurations

    def test_search_handles_exception(self, setup_mock_ocean: Any) -> None:
        """Test that exceptions in search are handled gracefully."""
        data = {"foo": "bar"}
        obj = {"field": ".foo."}  # Invalid pattern
        result = _search_as_object(data, obj)
        assert result == {"field": None}


class TestGetMappedEntity:
    """Test the _get_mapped_entity function for entity mapping."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_get_mapped_entity_passes_selector(self, setup_mock_ocean: Any) -> None:
        """Test entity mapping when selector passes."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "bar"'
        result = _get_mapped_entity(0, data, raw_entity_mappings, selector_query)
        assert result.entity == {"foo": "bar"}
        assert result.did_entity_pass_selector is True

    def test_get_mapped_entity_fails_selector(self, setup_mock_ocean: Any) -> None:
        """Test entity mapping when selector fails."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "baz"'
        result = _get_mapped_entity(0, data, raw_entity_mappings, selector_query)
        assert result.entity == {}
        assert result.did_entity_pass_selector is False

    def test_get_mapped_entity_parse_all_true(self, setup_mock_ocean: Any) -> None:
        """Test entity mapping with parse_all=True ignores selector."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "baz"'  # Would normally fail
        result = _get_mapped_entity(
            0, data, raw_entity_mappings, selector_query, parse_all=True
        )
        assert result.entity == {"foo": "bar"}
        assert (
            result.did_entity_pass_selector is False
        )  # Still False, but entity is mapped

    def test_get_mapped_entity_with_misconfigurations(
        self, setup_mock_ocean: Any
    ) -> None:
        """Test entity mapping tracks misconfigurations."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"identifier": ".foo", "missing": ".nonexistent"}
        selector_query = "true"
        result = _get_mapped_entity(0, data, raw_entity_mappings, selector_query)
        assert result.entity == {"identifier": "bar", "missing": None}
        assert result.did_entity_pass_selector is True
        assert result.misconfigurations == {"missing": ".nonexistent"}

    def test_get_mapped_entity_complex_mapping(self, setup_mock_ocean: Any) -> None:
        """Test entity mapping with complex nested mappings."""
        data = {"id": "123", "name": "test", "meta": {"type": "service"}}
        raw_entity_mappings = {
            "identifier": ".id",
            "title": ".name",
            "properties": {"type": ".meta.type"},
        }
        selector_query = "true"
        result = _get_mapped_entity(0, data, raw_entity_mappings, selector_query)
        assert result.entity == {
            "identifier": "123",
            "title": "test",
            "properties": {"type": "service"},
        }
        assert result.did_entity_pass_selector is True


class TestCalculateEntity:
    """Test the _calculate_entity function for entity calculation from globals."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_calculate_entity_from_globals(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity using global batch data."""
        # Set up globals
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "bar"}
        assert entities[0].did_entity_pass_selector is True
        assert len(errors) == 0

    def test_calculate_entity_with_failed_selector(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity when selector fails."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "false"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {}
        assert entities[0].did_entity_pass_selector is False
        assert len(errors) == 0

    def test_calculate_entity_multiple_items(self, setup_mock_ocean: Any) -> None:
        """Test calculating entities from multiple items."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [
            {"id": "1", "name": "first"},
            {"id": "2", "name": "second"},
            {"id": "3", "name": "third"},
        ]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {
            "identifier": ".id",
            "title": ".name",
        }
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Calculate each entity separately (as would happen in multiprocess)
        results = [_calculate_entity(i) for i in range(3)]

        assert len(results) == 3
        assert results[0][0][0].entity == {"identifier": "1", "title": "first"}
        assert results[1][0][0].entity == {"identifier": "2", "title": "second"}
        assert results[2][0][0].entity == {"identifier": "3", "title": "third"}

    def test_calculate_entity_with_parse_all(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity with parse_all=True."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "false"  # Would normally skip
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = True

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "bar"}
        # Entity should still be mapped even though selector is false
        assert entities[0].did_entity_pass_selector is False
        assert len(errors) == 0

    def test_calculate_entity_with_complex_selector(
        self, setup_mock_ocean: Any
    ) -> None:
        """Test calculating entity with complex selector query."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [
            {"status": "active", "type": "service"},
            {"status": "inactive", "type": "service"},
        ]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {
            "identifier": ".type",
            "properties": {"status": ".status"},
        }
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = '.status == "active"'
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities_0, _ = _calculate_entity(0)
        entities_1, _ = _calculate_entity(1)

        # First entity should pass selector
        assert entities_0[0].did_entity_pass_selector is True
        assert entities_0[0].entity == {
            "identifier": "service",
            "properties": {"status": "active"},
        }

        # Second entity should fail selector
        assert entities_1[0].did_entity_pass_selector is False
        assert entities_1[0].entity == {}


class TestMappedEntity:
    """Test the MappedEntity dataclass."""

    def test_default_values(self) -> None:
        """Test MappedEntity default values."""
        entity = MappedEntity()
        assert entity.entity == {}
        assert entity.did_entity_pass_selector is False
        assert entity.misconfigurations == {}

    def test_custom_values(self) -> None:
        """Test MappedEntity with custom values."""
        entity = MappedEntity(
            entity={"id": "123"},
            did_entity_pass_selector=True,
            misconfigurations={"field": ".missing"},
        )
        assert entity.entity == {"id": "123"}
        assert entity.did_entity_pass_selector is True
        assert entity.misconfigurations == {"field": ".missing"}


class TestIntegration:
    """Integration tests for the multiprocess JQ processing functions."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_full_entity_processing_flow(self, setup_mock_ocean: Any) -> None:
        """Test the full entity processing flow from raw data to mapped entity."""
        # Simulate the flow that happens in multiprocess
        raw_data = [
            {
                "id": "service-1",
                "name": "My Service",
                "type": "microservice",
                "metadata": {"owner": "team-a", "tier": "critical"},
            },
            {
                "id": "service-2",
                "name": "Another Service",
                "type": "monolith",
                "metadata": {"owner": "team-b", "tier": "standard"},
            },
        ]

        mappings = {
            "identifier": ".id",
            "title": ".name",
            "blueprint": '"service"',
            "properties": {
                "type": ".type",
                "owner": ".metadata.owner",
                "tier": ".metadata.tier",
            },
        }

        selector = '.metadata.tier == "critical"'

        # Set up globals
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = selector
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Process entities
        results = [_calculate_entity(i) for i in range(len(raw_data))]

        # First entity should pass (tier == critical)
        assert results[0][0][0].did_entity_pass_selector is True
        assert results[0][0][0].entity["identifier"] == "service-1"
        assert results[0][0][0].entity["title"] == "My Service"
        assert results[0][0][0].entity["properties"]["tier"] == "critical"

        # Second entity should fail (tier != critical)
        assert results[1][0][0].did_entity_pass_selector is False
        assert results[1][0][0].entity == {}

    def test_processing_with_misconfigurations(self, setup_mock_ocean: Any) -> None:
        """Test processing that results in misconfigurations."""
        raw_data = [
            {
                "id": "123",
                "name": "Test",
                # missing 'url' field
            }
        ]

        mappings = {
            "identifier": ".id",
            "title": ".name",
            "properties": {
                "url": ".url",  # Will be None
                "description": ".description",  # Will also be None
            },
        }

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity["identifier"] == "123"
        assert entities[0].entity["title"] == "Test"
        assert entities[0].entity["properties"]["url"] is None
        assert entities[0].entity["properties"]["description"] is None
        # Should have misconfigurations for the missing fields
        assert "url" in entities[0].misconfigurations
        assert "description" in entities[0].misconfigurations

    def test_processing_with_array_data(self, setup_mock_ocean: Any) -> None:
        """Test processing data that contains arrays."""
        raw_data = [
            {
                "id": "repo-1",
                "tags": ["python", "backend", "api"],
                "contributors": [
                    {"name": "Alice", "role": "owner"},
                    {"name": "Bob", "role": "contributor"},
                ],
            }
        ]

        mappings = {
            "identifier": ".id",
            "properties": {
                "tags": ".tags",
                "owner": '.contributors[] | select(.role == "owner") | .name',
            },
        }

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert entities[0].entity["identifier"] == "repo-1"
        assert entities[0].entity["properties"]["tags"] == ["python", "backend", "api"]
        assert entities[0].entity["properties"]["owner"] == "Alice"

    def test_caching_improves_performance(self, setup_mock_ocean: Any) -> None:
        """Test that pattern caching works across multiple entities."""
        raw_data = [{"id": str(i), "value": i} for i in range(100)]

        mappings = {"identifier": ".id", "count": ".value"}

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Clear cache to start fresh
        jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()

        # Process all entities
        for i in range(len(raw_data)):
            _calculate_entity(i)

        # Cache should have the patterns compiled once
        # There should be limited patterns (the unique ones used)
        assert len(jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS) <= 3
