"""Tests for the synchronous JQ entity processor.

These tests cover the JQEntityProcessorSync class which is used for
synchronous JQ processing in multiprocess contexts.
"""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from port_ocean.core.handlers.entity_processor import jq_entity_processor_sync
from port_ocean.core.handlers.entity_processor.jq_entity_processor_sync import (
    JQEntityProcessorSync,
)
from port_ocean.exceptions.core import EntityProcessorException


class TestJQEntityProcessorSync:
    """Test the synchronous JQ entity processor."""

    @pytest.fixture
    def mocked_processor(self, monkeypatch: Any) -> JQEntityProcessorSync:
        """Create a mocked processor with ocean config."""
        mock_ocean = MagicMock()
        mock_ocean.config = MagicMock()
        mock_ocean.config.allow_environment_variables_jq_access = True
        monkeypatch.setattr(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor_sync.ocean",
            mock_ocean,
        )
        processor = JQEntityProcessorSync()
        return processor

    def test_format_filter(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test that single quotes are converted to double quotes."""
        # Test single quotes at start
        result = mocked_processor._format_filter("'/' + .organization")
        assert result == '"/" + .organization'

        # Test single quotes at end
        result = mocked_processor._format_filter(".organization + '/'")
        assert result == '.organization + "/"'

        # Test single quotes in middle (should not be replaced)
        result = mocked_processor._format_filter(".organization + '/' + .repository")
        assert result == '.organization + "/" + .repository'

        # Test that double quotes are not affected
        result = mocked_processor._format_filter('"shalom"')
        assert result == '"shalom"'

    def test_compile(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test pattern compilation."""
        pattern = ".foo"
        compiled = mocked_processor._compile(pattern)
        assert compiled is not None

        # Test that same pattern returns cached version
        compiled2 = mocked_processor._compile(pattern)
        assert compiled is compiled2

    def test_compile_without_env_access(self, monkeypatch: Any) -> None:
        """Test compilation when environment variable access is disabled."""
        mock_ocean = MagicMock()
        mock_ocean.config = MagicMock()
        mock_ocean.config.allow_environment_variables_jq_access = False
        monkeypatch.setattr(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor_sync.ocean",
            mock_ocean,
        )
        processor = JQEntityProcessorSync()
        pattern = ".foo"
        compiled = processor._compile(pattern)
        assert compiled is not None

    def test_search(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test basic search functionality."""
        data = {"foo": "bar"}
        pattern = ".foo"
        result = mocked_processor._search(data, pattern)
        assert result == "bar"

    def test_search_with_single_quotes(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search with single quotes in pattern."""
        data = {"repository": "ocean", "organization": "port"}
        pattern = ".organization + '/' + .repository"
        result = mocked_processor._search(data, pattern)
        assert result == "port/ocean"

    def test_search_with_single_quotes_in_the_end(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search with single quotes at the end."""
        data = {"organization": "port"}
        pattern = ".organization + '/'"
        result = mocked_processor._search(data, pattern)
        assert result == "port/"

    def test_search_with_single_quotes_in_the_start(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search with single quotes at the start."""
        data = {"organization": "port"}
        pattern = "'/' + .organization"
        result = mocked_processor._search(data, pattern)
        assert result == "/port"

    def test_search_returns_none_on_error(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test that search returns None on JQ errors."""
        data = {"foo": "bar"}
        pattern = ".foo."  # Invalid pattern
        result = mocked_processor._search(data, pattern)
        assert result is None

    def test_search_with_double_quotes(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search with double quotes in pattern."""
        data = {"foo": "bar"}
        pattern = '"shalom"'
        result = mocked_processor._search(data, pattern)
        assert result == "shalom"

    def test_search_returns_list(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test that search can return a list."""
        data = {"parameters": ["parameter_value", "another_value", "another_value2"]}
        pattern = ".parameters"
        result = mocked_processor._search(data, pattern)
        assert result == ["parameter_value", "another_value", "another_value2"]

    @pytest.mark.parametrize(
        "pattern, expected",
        [
            ('.parameters[] | select(.name == "not_exists") | .value', None),
            (
                '.parameters[] | select(.name == "parameter_name") | .value',
                "parameter_value",
            ),
            (
                '.parameters[] | select(.name == "another_parameter") | .value',
                "another_value",
            ),
        ],
    )
    def test_search_with_select(
        self,
        mocked_processor: JQEntityProcessorSync,
        pattern: str,
        expected: Any,
    ) -> None:
        """Test search with select expressions."""
        data = {
            "parameters": [
                {"name": "parameter_name", "value": "parameter_value"},
                {"name": "another_parameter", "value": "another_value"},
                {"name": "another_parameter", "value": "another_value2"},
            ]
        }
        result = mocked_processor._search(data, pattern)
        assert result == expected

    def test_search_as_bool(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test search_as_bool with boolean values."""
        data = {"foo": True}
        pattern = ".foo"
        result = mocked_processor._search_as_bool(data, pattern)
        assert result is True

        data = {"foo": False}
        result = mocked_processor._search_as_bool(data, pattern)
        assert result is False

    def test_search_as_bool_failure(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test that search_as_bool raises exception for non-boolean values."""
        data = {"foo": "bar"}
        pattern = ".foo"
        with pytest.raises(
            EntityProcessorException,
            match="Expected boolean value, got value:bar of type: <class 'str'> instead",
        ):
            mocked_processor._search_as_bool(data, pattern)

    def test_search_as_object(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test search_as_object with simple object mapping."""
        data = {"foo": {"bar": "baz"}}
        obj = {"foo": ".foo.bar"}
        result = mocked_processor._search_as_object(data, obj)
        assert result == {"foo": "baz"}

    def test_search_as_object_with_nested_dict(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search_as_object with nested dictionaries."""
        data = {"foo": {"bar": {"baz": "qux"}}}
        obj = {"foo": {"bar": ".foo.bar.baz"}}
        result = mocked_processor._search_as_object(data, obj)
        assert result == {"foo": {"bar": "qux"}}

    def test_search_as_object_with_list(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search_as_object with list values (multiple mapping templates)."""
        data = {"id": "1", "name": "first", "value": 100}
        # List contains multiple mapping templates applied to the same data
        obj = {
            "mappings": [
                {"id": ".id", "name": ".name"},
                {"id": ".id", "value": ".value"},
            ]
        }
        result = mocked_processor._search_as_object(data, obj)
        mappings = cast(list[dict[str, Any]], result["mappings"])
        assert len(mappings) == 2
        assert mappings[0]["id"] == "1"
        assert mappings[0]["name"] == "first"
        assert mappings[1]["id"] == "1"
        assert mappings[1]["value"] == 100

    def test_search_as_object_with_misconfigurations(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test that misconfigurations are tracked."""
        data = {"foo": "bar"}
        obj = {"missing": ".missing_field"}
        misconfigurations: dict[str, str] = {}
        result = mocked_processor._search_as_object(data, obj, misconfigurations)
        assert result == {"missing": None}
        assert "missing" in misconfigurations
        assert misconfigurations["missing"] == ".missing_field"

    def test_search_as_object_handles_errors(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test that search_as_object handles errors gracefully."""
        data = {"foo": {"bar": "baz"}}
        obj = {"foo": ".foo.bar."}  # Invalid pattern
        result = mocked_processor._search_as_object(data, obj)
        assert result == {"foo": None}

    def test_get_mapped_entity(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test get_mapped_entity with passing selector."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "bar"'
        result = mocked_processor._get_mapped_entity(
            data, raw_entity_mappings, selector_query
        )
        assert result.entity == {"foo": "bar"}
        assert result.did_entity_pass_selector is True
        assert result.misconfigurations == {}

    def test_get_mapped_entity_with_failed_selector(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test get_mapped_entity with failing selector."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "baz"'
        result = mocked_processor._get_mapped_entity(
            data, raw_entity_mappings, selector_query
        )
        assert result.entity == {}
        assert result.did_entity_pass_selector is False

    def test_get_mapped_entity_with_parse_all(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test get_mapped_entity with parse_all=True."""
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = "false"  # Selector fails
        result = mocked_processor._get_mapped_entity(
            data, raw_entity_mappings, selector_query, parse_all=True
        )
        # Entity should still be mapped even though selector fails
        assert result.entity == {"foo": "bar"}
        assert result.did_entity_pass_selector is False

    def test_get_mapped_entity_with_misconfigurations(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test get_mapped_entity tracks misconfigurations."""
        data = {"foo": "bar"}
        raw_entity_mappings = {
            "foo": ".foo",
            "missing": ".missing_field",
        }
        selector_query = "true"
        result = mocked_processor._get_mapped_entity(
            data, raw_entity_mappings, selector_query
        )
        assert result.entity == {"foo": "bar", "missing": None}
        assert "missing" in result.misconfigurations

    def test_pattern_caching(self, mocked_processor: JQEntityProcessorSync) -> None:
        """Test that patterns are cached correctly."""
        pattern = ".foo"
        compiled1 = mocked_processor._compile(pattern)
        compiled2 = mocked_processor._compile(pattern)
        assert compiled1 is compiled2
        # Access the module-level cache - the pattern stored is the formatted one
        formatted_pattern = JQEntityProcessorSync._format_filter(pattern)
        # Since allow_environment_variables_jq_access is True in the fixture,
        # the pattern stored should be just the formatted pattern
        assert formatted_pattern in jq_entity_processor_sync._COMPILED_PATTERNS
        # Verify the cached compiled pattern is the same object
        assert (
            jq_entity_processor_sync._COMPILED_PATTERNS[formatted_pattern] is compiled1
        )

    def test_compile_patterns_initialization(self) -> None:
        """Test that _COMPILED_PATTERNS is a dict that can store compiled patterns."""
        # Clear the module-level cache first since it's shared
        jq_entity_processor_sync._COMPILED_PATTERNS.clear()
        assert jq_entity_processor_sync._COMPILED_PATTERNS == {}
        assert isinstance(jq_entity_processor_sync._COMPILED_PATTERNS, dict)

    def test_search_with_complex_selector(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search with complex selector expressions."""
        data = {
            "status": "active",
            "type": "service",
            "metadata": {"tier": "critical"},
        }
        selector = '.status == "active"'
        result = mocked_processor._search_as_bool(data, selector)
        assert result is True

        selector = '.metadata.tier == "critical"'
        result = mocked_processor._search_as_bool(data, selector)
        assert result is True

    def test_search_as_object_with_complex_nesting(
        self, mocked_processor: JQEntityProcessorSync
    ) -> None:
        """Test search_as_object with complex nested structures."""
        data = {
            "id": "service-1",
            "name": "My Service",
            "metadata": {
                "owner": "team-a",
                "tier": "critical",
                "tags": ["python", "backend"],
            },
        }
        obj = {
            "identifier": ".id",
            "title": ".name",
            "properties": {
                "owner": ".metadata.owner",
                "tier": ".metadata.tier",
                "tags": ".metadata.tags",
            },
        }
        result = mocked_processor._search_as_object(data, obj)
        properties = cast(dict[str, Any], result["properties"])

        assert result["identifier"] == "service-1"
        assert result["title"] == "My Service"
        assert properties["owner"] == "team-a"
        assert properties["tier"] == "critical"
        assert properties["tags"] == ["python", "backend"]
