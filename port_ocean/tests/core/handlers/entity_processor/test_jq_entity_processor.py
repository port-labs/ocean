from io import StringIO
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from loguru import logger

from port_ocean.context.ocean import PortOceanContext, ocean
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult
from port_ocean.exceptions.core import EntityProcessorException


@pytest.mark.asyncio
class TestJQEntityProcessor:
    @pytest.fixture
    def mocked_processor(self, monkeypatch: Any) -> JQEntityProcessor:
        mock_context = AsyncMock()
        mock_context.config = MagicMock()
        mock_context.config.process_in_queue_max_workers = 4
        mock_context.config.process_in_queue_timeout = 10
        mock_context.config.allow_environment_variables_jq_access = True
        monkeypatch.setattr(PortOceanContext, "app", mock_context)
        ocean._app = mock_context
        processor = JQEntityProcessor(mock_context)
        # Set up entity_processor for multiprocess access in _calculate_entity
        mock_context.integration = MagicMock()
        mock_context.integration.entity_processor = processor
        return processor

    async def test_compile(self, mocked_processor: JQEntityProcessor) -> None:
        pattern = ".foo"
        compiled = mocked_processor._compile(pattern)
        assert compiled is not None

    async def test_search(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": "bar"}
        pattern = ".foo"
        result = await mocked_processor._search(data, pattern)
        assert result == "bar"

    async def test_search_with_single_quotes(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"repository": "ocean", "organization": "port"}
        pattern = ".organization + '/' + .repository"
        result = await mocked_processor._search(data, pattern)
        assert result == "port/ocean"

    async def test_search_with_single_quotes_in_the_end(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"organization": "port"}
        pattern = ".organization + '/'"
        result = await mocked_processor._search(data, pattern)
        assert result == "port/"

    async def test_search_with_single_quotes_in_the_start(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"organization": "port"}
        pattern = "'/' + .organization"
        result = await mocked_processor._search(data, pattern)
        assert result == "/port"

    async def test_search_as_bool(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": True}
        pattern = ".foo"
        result = await mocked_processor._search_as_bool(data, pattern)
        assert result is True

    async def test_search_as_object(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": {"bar": "baz"}}
        obj = {"foo": ".foo.bar"}
        result = await mocked_processor._search_as_object(data, obj)
        assert result == {"foo": "baz"}

    async def test_get_mapped_entity(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "bar"'
        result = await mocked_processor._get_mapped_entity(
            data, raw_entity_mappings, selector_query
        )
        assert result.entity == {"foo": "bar"}
        assert result.did_entity_pass_selector is True

    async def test_parse_items(self, mocked_processor: JQEntityProcessor) -> None:
        mapping = Mock()
        mapping.port.entity.mappings.dict.return_value = {
            "identifier": ".foo",
            "blueprint": ".foo",
            "properties": {"foo": ".foo"},
        }
        mapping.port.items_to_parse = None
        mapping.selector.query = '.foo == "bar"'
        raw_results = [{"foo": "bar"}]
        result = await mocked_processor._parse_items(mapping, raw_results)
        assert isinstance(result, CalculationResult)
        assert len(result.entity_selector_diff.passed) == 1
        assert result.entity_selector_diff.passed[0].properties.get("foo") == "bar"
        assert not result.errors

    async def test_in_operator(self, mocked_processor: JQEntityProcessor) -> None:
        data = {
            "key": "GetPort_SelfService",
            "name": "GetPort SelfService",
            "desc": "Test",
            "qualifier": "VW",
            "visibility": "public",
            "selectionMode": "NONE",
            "subViews": [
                {
                    "key": "GetPort_SelfService_Second",
                    "name": "GetPort SelfService Second",
                    "qualifier": "SVW",
                    "selectionMode": "NONE",
                    "subViews": [
                        {
                            "key": "GetPort_SelfService_Third",
                            "name": "GetPort SelfService Third",
                            "qualifier": "SVW",
                            "selectionMode": "NONE",
                            "subViews": [],
                            "referencedBy": [],
                        },
                        {
                            "key": "Port_Test",
                            "name": "Port Test",
                            "qualifier": "SVW",
                            "selectionMode": "NONE",
                            "subViews": [],
                            "referencedBy": [],
                        },
                    ],
                    "referencedBy": [],
                },
                {
                    "key": "Python",
                    "name": "Python",
                    "qualifier": "SVW",
                    "selectionMode": "NONE",
                    "subViews": [
                        {
                            "key": "Time",
                            "name": "Time",
                            "qualifier": "SVW",
                            "selectionMode": "NONE",
                            "subViews": [
                                {
                                    "key": "port_*****",
                                    "name": "port-*****",
                                    "qualifier": "SVW",
                                    "selectionMode": "NONE",
                                    "subViews": [
                                        {
                                            "key": "port_*****:REferenced",
                                            "name": "REferenced",
                                            "qualifier": "VW",
                                            "visibility": "public",
                                            "originalKey": "REferenced",
                                        }
                                    ],
                                    "referencedBy": [],
                                }
                            ],
                            "referencedBy": [],
                        }
                    ],
                    "referencedBy": [],
                },
                {
                    "key": "GetPort_SelfService:Authentication_Application",
                    "name": "Authentication Application",
                    "desc": "For auth services",
                    "qualifier": "APP",
                    "visibility": "private",
                    "selectedBranches": ["main"],
                    "originalKey": "Authentication_Application",
                },
            ],
            "referencedBy": [],
        }
        pattern = '.subViews | map(select((.qualifier | IN("VW", "SVW"))) | .key)'
        result = await mocked_processor._search(data, pattern)
        assert result == ["GetPort_SelfService_Second", "Python"]

    async def test_failure_of_jq_expression(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"foo": "bar"}
        pattern = ".foo."
        result = await mocked_processor._search(data, pattern)
        assert result is None

    async def test_search_as_object_failure(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"foo": {"bar": "baz"}}
        obj = {"foo": ".foo.bar."}
        result = await mocked_processor._search_as_object(data, obj)
        assert result == {"foo": None}

    async def test_double_quotes_in_jq_expression(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"foo": "bar"}
        pattern = '"shalom"'
        result = await mocked_processor._search(data, pattern)
        assert result == "shalom"

    async def test_search_as_bool_failure(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"foo": "bar"}
        pattern = ".foo"
        with pytest.raises(
            EntityProcessorException,
            match="Expected boolean value, got value:bar of type: <class 'str'> instead",
        ):
            await mocked_processor._search_as_bool(data, pattern)

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
    async def test_search_fails_on_stop_iteration(
        self, mocked_processor: JQEntityProcessor, pattern: str, expected: Any
    ) -> None:
        data = {
            "parameters": [
                {"name": "parameter_name", "value": "parameter_value"},
                {"name": "another_parameter", "value": "another_value"},
                {"name": "another_parameter", "value": "another_value2"},
            ]
        }
        result = await mocked_processor._search(data, pattern)
        assert result == expected

    async def test_return_a_list_of_values(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        data = {"parameters": ["parameter_value", "another_value", "another_value2"]}
        pattern = ".parameters"
        result = await mocked_processor._search(data, pattern)
        assert result == ["parameter_value", "another_value", "another_value2"]

    @pytest.mark.timeout(3)
    async def test_search_performance_10000(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """
        This test is to check the performance of the search method when called 10000 times.
        """
        data = {"foo": "bar"}
        pattern = ".foo"
        for _ in range(10000):
            result = await mocked_processor._search(data, pattern)
            assert result == "bar"

    @pytest.mark.timeout(30)
    async def test_parse_items_performance_10000(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """
        This test is to check the performance of the parse_items method when called 10000 times.
        """
        mapping = Mock()
        mapping.port.entity.mappings.dict.return_value = {
            "identifier": ".foo",
            "blueprint": ".foo",
            "properties": {"foo": ".foo"},
        }
        mapping.port.items_to_parse = None
        mapping.selector.query = '.foo == "bar"'
        raw_results = [{"foo": "bar"} for _ in range(10000)]

        item = await mocked_processor._parse_items(mapping, raw_results)
        assert isinstance(item, CalculationResult)
        assert len(item.entity_selector_diff.passed) == 10000
        assert item.entity_selector_diff.passed[0].properties.get("foo") == "bar"
        assert not item.errors

    async def test_parse_items_wrong_mapping(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        mapping = Mock()
        mapping.port.entity.mappings.dict.return_value = {
            "title": ".foo",
            "identifier": ".ark",
            "blueprint": ".baz",
            "properties": {
                "description": ".bazbar",
                "url": ".foobar",
                "defaultBranch": ".bar.baz",
            },
        }
        mapping.port.items_to_parse = None
        mapping.selector.query = "true"
        raw_results = [
            {
                "foo": "bar",
                "baz": "bazbar",
                "bar": {"foobar": "barfoo", "baz": "barbaz"},
            },
            {"foo": "bar", "baz": "bazbar", "bar": {"foobar": "foobar"}},
        ]
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor._send_examples"
        ) as mock_send_examples:
            result = await mocked_processor._parse_items(
                mapping, raw_results, send_raw_data_examples_amount=1
            )
            assert len(result.misconfigured_entity_keys) > 0
            assert len(result.misconfigured_entity_keys) == 4
            assert result.misconfigured_entity_keys == {
                "identifier": ".ark",
                "description": ".bazbar",
                "url": ".foobar",
                "defaultBranch": ".bar.baz",
            }
            assert mock_send_examples.await_args is not None, "mock was not awaited"
            args, _ = mock_send_examples.await_args
            assert len(cast(list[Any], args[0])) > 0

    async def test_parse_items_empty_required(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        stream = StringIO()
        sink_id = logger.add(stream, level="DEBUG")

        mapping = Mock()
        mapping.port.entity.mappings.dict.return_value = {
            "identifier": ".foo",
            "blueprint": ".bar",
        }
        mapping.port.items_to_parse = None
        mapping.selector.query = "true"
        raw_results: list[dict[Any, Any]] = [
            {"foo": "", "bar": "bluePrintMapped"},
            {"foo": "identifierMapped", "bar": ""},
        ]
        result = await mocked_processor._parse_items(mapping, raw_results)
        assert "identifier" not in result.misconfigured_entity_keys
        assert "blueprint" not in result.misconfigured_entity_keys

        raw_results = [
            {"foo": "identifierMapped", "bar": None},
            {"foo": None, "bar": ""},
        ]
        result = await mocked_processor._parse_items(mapping, raw_results)
        assert result.misconfigured_entity_keys == {
            "identifier": ".foo",
            "blueprint": ".bar",
        }

        logger.remove(sink_id)
        logs_captured = stream.getvalue()

        assert (
            "2 transformations of batch failed due to empty, null or missing values"
            in logs_captured
        )
        assert (
            "{'blueprint': '.bar', 'identifier': '.foo'} (null, missing, or misconfigured)"
            in logs_captured
        )

    async def test_examples_sent_even_when_transformation_fails(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """
        Test that kind examples are sent BEFORE transformation, so users can see
        raw data even when the mapping fails completely.

        Scenario: Raw data has user objects with 'name' and 'email', but the mapping
        tries to use '.test' as identifier (which doesn't exist). Transformation
        should fail, but examples should still be sent.
        """
        mapping = Mock()
        mapping.kind = "users"
        mapping.port.entity.mappings.dict.return_value = {
            "identifier": ".test",  # This field doesn't exist in raw data
            "blueprint": '"user"',
            "properties": {
                "name": ".name",
                "email": ".email",
            },
        }
        mapping.port.items_to_parse = None
        mapping.port.items_to_parse_name = "item"
        mapping.selector.query = "true"

        # Raw data - users with name and email, but NO .color field
        raw_results = [
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Jane Smith", "email": "jane@example.com"},
            {"name": "Bob Wilson", "email": "bob@example.com"},
        ]

        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.JQEntityProcessor._send_examples"
        ) as mock_send_examples:
            result = await mocked_processor._parse_items(
                mapping, raw_results, send_raw_data_examples_amount=2
            )

            # Verify examples were sent (this is the key assertion)
            assert (
                mock_send_examples.await_args is not None
            ), "Examples should be sent even when transformation fails"

            # Verify the raw data was sent as examples
            args, _ = mock_send_examples.await_args
            examples_sent = cast(list[Any], args[0])
            assert len(examples_sent) == 2, "Should send requested number of examples"

            # Verify examples contain the raw data
            assert examples_sent[0] == {"name": "John Doe", "email": "john@example.com"}
            assert examples_sent[1] == {
                "name": "Jane Smith",
                "email": "jane@example.com",
            }

            # Verify the kind was passed correctly
            kind_arg = args[1]
            assert kind_arg == "users"

            # Verify transformation failed (no entities created because .color doesn't exist)
            assert (
                len(result.entity_selector_diff.passed) == 0
            ), "No entities should pass because identifier mapping failed"

            # Verify misconfigurations were detected
            assert (
                "identifier" in result.misconfigured_entity_keys
            ), "Should report identifier as misconfigured"

    async def test_separate_compileable_and_uncompileable_patterns_simple(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test separating compileable and uncompileable patterns with simple patterns."""
        raw_entity_mappings = {
            "identifier": ".id",
            "title": ".name",
            "invalid": ".invalid.",
        }
        compileable, uncompileable = (
            await mocked_processor.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                raw_entity_mappings
            )
        )
        assert "identifier" in compileable
        assert "title" in compileable
        assert compileable["identifier"] == ".id"
        assert compileable["title"] == ".name"
        assert "invalid" in uncompileable
        assert uncompileable["invalid"] == ".invalid."

    async def test_separate_compileable_and_uncompileable_patterns_nested(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test separating compileable and uncompileable patterns with nested dictionaries."""
        raw_entity_mappings = {
            "identifier": ".id",
            "properties": {
                "name": ".name",
                "invalid": ".invalid.",
                "nested": {
                    "value": ".value",
                    "broken": ".broken.",
                },
            },
        }
        compileable, uncompileable = (
            await mocked_processor.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                raw_entity_mappings
            )
        )
        assert "identifier" in compileable
        assert "properties" in compileable
        # Nested dicts are split - compileable patterns go to compileable, uncompileable go to uncompileable
        assert compileable["properties"]["name"] == ".name"
        assert compileable["properties"]["nested"]["value"] == ".value"
        assert "invalid" in uncompileable["properties"]
        assert uncompileable["properties"]["invalid"] == ".invalid."
        assert "broken" in uncompileable["properties"]["nested"]
        assert uncompileable["properties"]["nested"]["broken"] == ".broken."

    async def test_separate_compileable_and_uncompileable_patterns_with_selector(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test that selector queries are compiled during warmup."""
        raw_entity_mappings = {"identifier": ".id"}
        selector_queries = [".status == 'active'"]
        compileable, uncompileable = (
            await mocked_processor.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                raw_entity_mappings, selector_queries
            )
        )
        assert "identifier" in compileable
        # Selector queries are compiled but not returned, just warmed up

    async def test_separate_compileable_and_uncompileable_patterns_empty(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test with empty mappings."""
        compileable, uncompileable = (
            await mocked_processor.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                {}
            )
        )
        assert compileable == {}
        assert uncompileable == {}

    async def test_parse_items_sync_basic(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items synchronously with valid patterns."""
        compileable_patterns = {
            "identifier": ".id",
            "title": ".name",
        }
        raw_results = [
            {"id": "1", "name": "First"},
            {"id": "2", "name": "Second"},
        ]
        selector_query = "true"
        results, errors = await mocked_processor.parse_items_sync(
            compileable_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 2
        assert len(results[0][0]) == 1
        assert results[0][0][0].entity["identifier"] == "1"
        assert results[0][0][0].entity["title"] == "First"
        assert results[1][0][0].entity["identifier"] == "2"
        assert results[1][0][0].entity["title"] == "Second"

    async def test_parse_items_sync_with_selector(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items synchronously with selector query."""
        compileable_patterns = {"identifier": ".id"}
        raw_results = [
            {"id": "1", "status": "active"},
            {"id": "2", "status": "inactive"},
        ]
        selector_query = '.status == "active"'
        results, errors = await mocked_processor.parse_items_sync(
            compileable_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 2
        assert results[0][0][0].did_entity_pass_selector is True
        assert results[1][0][0].did_entity_pass_selector is False

    async def test_parse_items_sync_with_parse_all(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items synchronously with parse_all=True."""
        compileable_patterns = {"identifier": ".id"}
        raw_results = [{"id": "1"}]
        selector_query = "false"
        results, errors = await mocked_processor.parse_items_sync(
            compileable_patterns, raw_results, selector_query, parse_all=True
        )
        assert len(errors) == 0
        assert len(results) == 1
        assert results[0][0][0].entity["identifier"] == "1"
        assert results[0][0][0].did_entity_pass_selector is False

    async def test_parse_items_sync_empty_results(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items synchronously with empty results."""
        compileable_patterns = {"identifier": ".id"}
        raw_results: list[dict[str, Any]] = []
        selector_query = "true"
        results, errors = await mocked_processor.parse_items_sync(
            compileable_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 0

    async def test_parse_items_async_basic(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items asynchronously with valid patterns."""
        uncompiled_patterns = {
            "identifier": ".id",
            "title": ".name",
        }
        raw_results = [
            {"id": "1", "name": "First"},
            {"id": "2", "name": "Second"},
        ]
        selector_query = "true"
        results, errors = await mocked_processor.parse_items_async(
            uncompiled_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 2
        assert len(results[0][0]) == 1
        assert results[0][0][0].entity["identifier"] == "1"
        assert results[0][0][0].entity["title"] == "First"

    async def test_parse_items_async_empty_patterns(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items asynchronously with empty patterns."""
        uncompiled_patterns: dict[str, Any] = {}
        raw_results = [{"id": "1"}]
        selector_query = "true"
        results, errors = await mocked_processor.parse_items_async(
            uncompiled_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 0

    async def test_parse_items_async_with_selector(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test parsing items asynchronously with selector query."""
        uncompiled_patterns = {"identifier": ".id"}
        raw_results = [
            {"id": "1", "active": True},
            {"id": "2", "active": False},
        ]
        selector_query = ".active == true"
        results, errors = await mocked_processor.parse_items_async(
            uncompiled_patterns, raw_results, selector_query
        )
        assert len(errors) == 0
        assert len(results) == 2
        assert results[0][0][0].did_entity_pass_selector is True
        assert results[1][0][0].did_entity_pass_selector is False

    async def test_deep_merge_basic(self, mocked_processor: JQEntityProcessor) -> None:
        """Test basic deep merge functionality."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        result = mocked_processor._deep_merge(dict1, dict2)
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}
        assert dict1 == {"a": 1, "b": 2, "c": 3, "d": 4}  # dict1 is modified in place

    async def test_deep_merge_nested(self, mocked_processor: JQEntityProcessor) -> None:
        """Test deep merge with nested dictionaries."""
        dict1 = {"a": {"x": 1, "y": 2}, "b": 3}
        dict2 = {"a": {"z": 4}, "c": 5}
        result = mocked_processor._deep_merge(dict1, dict2)
        assert result == {"a": {"x": 1, "y": 2, "z": 4}, "b": 3, "c": 5}

    async def test_deep_merge_overwrite(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test that deep merge doesn't overwrite existing values."""
        dict1 = {"a": {"x": 1}, "b": 2}
        dict2 = {"a": {"y": 3}, "b": 4}
        result = mocked_processor._deep_merge(dict1, dict2)
        # Only new keys are added, existing keys are preserved
        assert result == {"a": {"x": 1, "y": 3}, "b": 2}

    async def test_deep_merge_empty_dicts(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test deep merge with empty dictionaries."""
        dict1: dict[str, Any] = {}
        dict2 = {"a": 1}
        result = mocked_processor._deep_merge(dict1, dict2)
        assert result == {"a": 1}

    async def test_merge_results_both_jq_and_async(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test merging results when both jq and async results exist."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"identifier": "1", "jq_field": "jq_value"},
                            did_entity_pass_selector=True,
                        )
                    ],
                    [],
                ),
                (
                    [
                        MappedEntity(
                            entity={"identifier": "2", "jq_field": "jq_value2"},
                            did_entity_pass_selector=True,
                        )
                    ],
                    [],
                ),
            ],
            [],
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"async_field": "async_value"},
                            did_entity_pass_selector=True,
                        )
                    ],
                    [],
                ),
                (
                    [
                        MappedEntity(
                            entity={"async_field": "async_value2"},
                            did_entity_pass_selector=True,
                        )
                    ],
                    [],
                ),
            ],
            [],
        )
        raw_results = [{"id": "1"}, {"id": "2"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        assert len(errors) == 0
        assert len(entities) == 2
        assert entities[0].entity == {
            "identifier": "1",
            "jq_field": "jq_value",
            "async_field": "async_value",
        }
        assert entities[0].did_entity_pass_selector is True
        assert entities[1].entity == {
            "identifier": "2",
            "jq_field": "jq_value2",
            "async_field": "async_value2",
        }

    async def test_merge_results_only_jq(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test merging results when only jq results exist."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"identifier": "1"}, did_entity_pass_selector=True
                        )
                    ],
                    [],
                )
            ],
            [],
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = ([], [])
        raw_results: list[RAW_ITEM] = [{"id": "1"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        assert len(errors) == 0
        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "1"}

    async def test_merge_results_only_async(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test merging results when only async results exist."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = ([([], [])], [])
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"identifier": "1"}, did_entity_pass_selector=True
                        )
                    ],
                    [],
                )
            ],
            [],
        )
        raw_results = [{"id": "1"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        assert len(errors) == 0
        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "1"}

    async def test_merge_results_with_top_level_errors(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test merging results with top-level errors raises ExceptionGroup."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [MappedEntity(entity={"identifier": "1"})],
                    [],
                )
            ],
            [ValueError("Top-level JQ error")],  # Top-level error
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [MappedEntity(entity={"identifier": "1"})],
                    [],
                )
            ],
            [],
        )
        raw_results = [{"id": "1"}]
        with pytest.raises(ExceptionGroup, match="Error processing tasks"):
            mocked_processor.merge_results(jq_results, async_results, raw_results)

    async def test_merge_results_with_per_item_errors(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test merging results with per-item errors adds them to errors list."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [MappedEntity(entity={"identifier": "1"})],
                    [ValueError("JQ error")],  # Per-item error
                )
            ],
            [],  # No top-level errors
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [MappedEntity(entity={"identifier": "1"})],
                    [RuntimeError("Async error")],  # Per-item error
                )
            ],
            [],  # No top-level errors
        )
        raw_results: list[RAW_ITEM] = [{"id": "1"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        # Per-item errors are collected but don't raise ExceptionGroup
        assert len(errors) == 2
        assert len(entities) == 1

    async def test_merge_results_selector_logic(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test that merged entity passes selector only if both pass."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"identifier": "1"}, did_entity_pass_selector=True
                        )
                    ],
                    [],
                ),
                (
                    [
                        MappedEntity(
                            entity={"identifier": "2"}, did_entity_pass_selector=False
                        )
                    ],
                    [],
                ),
            ],
            [],
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={}, did_entity_pass_selector=True
                        )  # First passes
                    ],
                    [],
                ),
                (
                    [
                        MappedEntity(
                            entity={}, did_entity_pass_selector=True
                        )  # Second passes
                    ],
                    [],
                ),
            ],
            [],
        )
        raw_results: list[RAW_ITEM] = [{"id": "1"}, {"id": "2"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        assert len(errors) == 0
        assert len(entities) == 2
        # First: True && True = True
        assert entities[0].did_entity_pass_selector is True
        # Second: False && True = False
        assert entities[1].did_entity_pass_selector is False

    async def test_merge_results_misconfigurations(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test that misconfigurations are merged correctly."""
        from port_ocean.core.handlers.entity_processor.models import MappedEntity

        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={"identifier": "1"},
                            misconfigurations={"jq_field": ".jq_field"},
                        )
                    ],
                    [],
                )
            ],
            [],
        )
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ] = (
            [
                (
                    [
                        MappedEntity(
                            entity={},
                            misconfigurations={"async_field": ".async_field"},
                        )
                    ],
                    [],
                )
            ],
            [],
        )
        raw_results: list[RAW_ITEM] = [{"id": "1"}]
        entities, errors = mocked_processor.merge_results(
            jq_results, async_results, raw_results
        )
        assert len(errors) == 0
        assert len(entities) == 1
        assert entities[0].misconfigurations == {
            "jq_field": ".jq_field",
            "async_field": ".async_field",
        }
