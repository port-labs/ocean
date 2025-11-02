from typing import cast, Any
from unittest.mock import AsyncMock, Mock
from loguru import logger
import pytest
from io import StringIO

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.ocean_types import CalculationResult
from port_ocean.exceptions.core import EntityProcessorException
from unittest.mock import patch


@pytest.mark.asyncio
class TestJQEntityProcessor:

    @pytest.fixture
    def mocked_processor(self, monkeypatch: Any) -> JQEntityProcessor:
        mock_context = AsyncMock()
        monkeypatch.setattr(PortOceanContext, "app", mock_context)
        return JQEntityProcessor(mock_context)

    async def test_compile(self, mocked_processor: JQEntityProcessor) -> None:
        pattern = ".foo"
        compiled = mocked_processor._compile(pattern)
        assert compiled is not None

    async def test_search(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": "bar"}
        pattern = ".foo"
        result = await mocked_processor._search(data, pattern)
        assert result == "bar"

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
            data, raw_entity_mappings, None, selector_query
        )
        assert result.entity == {"foo": "bar"}
        assert result.did_entity_pass_selector is True

    async def test_calculate_entity(self, mocked_processor: JQEntityProcessor) -> None:
        data = {"foo": "bar"}
        raw_entity_mappings = {"foo": ".foo"}
        selector_query = '.foo == "bar"'
        result, errors = await mocked_processor._calculate_entity(
            data, raw_entity_mappings, None, "item", selector_query
        )
        assert len(result) == 1
        assert result[0].entity == {"foo": "bar"}
        assert result[0].did_entity_pass_selector is True
        assert not errors

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
        raw_results = [{"foo": "bar"}]
        for _ in range(10000):
            result = await mocked_processor._parse_items(mapping, raw_results)
            assert isinstance(result, CalculationResult)
            assert len(result.entity_selector_diff.passed) == 1
            assert result.entity_selector_diff.passed[0].properties.get("foo") == "bar"
            assert not result.errors

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

    async def test_build_raw_entity_mappings_string_values(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test _build_raw_entity_mappings with string values that evaluate to different InputEvaluationResult types"""
        raw_entity_mappings = {
            "identifier": ".item.id",  # SINGLE - contains pattern
            "title": ".item.name",  # SINGLE - contains pattern
            "blueprint": ".item.type",  # SINGLE - contains pattern
            "icon": ".item.icon",  # SINGLE - contains pattern
            "team": ".item.team",  # SINGLE - contains pattern
            "properties": {
                "status": ".item.status",  # SINGLE - contains pattern
                "description": ".item.desc",  # SINGLE - contains pattern
                "external_ref": ".external.ref",  # ALL - contains dots but not pattern
                "static_value": '"static"',  # NONE - no pattern, no dots
            },
            "relations": {
                "owner": ".item.owner",  # SINGLE - contains pattern
                "parent": ".item.parent",  # SINGLE - contains pattern
                "external_relation": ".external.relation",  # ALL - contains dots but not pattern
                "null_value": "null",  # NONE - nullary expression
            },
        }
        items_to_parse_name = "item"

        single, all_items, none = mocked_processor._build_raw_entity_mappings(
            raw_entity_mappings, items_to_parse_name
        )

        # SINGLE mappings should contain all fields that reference .item
        expected_single = {
            "identifier": ".item.id",
            "title": ".item.name",
            "blueprint": ".item.type",
            "icon": ".item.icon",
            "team": ".item.team",
            "properties": {
                "status": ".item.status",
                "description": ".item.desc",
            },
            "relations": {
                "owner": ".item.owner",
                "parent": ".item.parent",
            },
        }
        assert single == expected_single

        # ALL mappings should contain fields that reference other patterns
        expected_all = {
            "properties": {
                "external_ref": ".external.ref",
            },
            "relations": {
                "external_relation": ".external.relation",
            },
        }
        assert all_items == expected_all

        # NONE mappings should contain nullary expressions
        expected_none = {
            "properties": {
                "static_value": '"static"',
            },
            "relations": {
                "null_value": "null",
            },
        }
        assert none == expected_none

    async def test_group_string_mapping_value(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_string_mapping_value function with various string values"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        # Test with different input evaluation results
        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test SINGLE evaluation (contains pattern)
        mocked_processor.group_string_mapping_value(
            "item", mappings, "identifier", ".item.id"
        )
        assert mappings[InputClassifyingResult.SINGLE]["identifier"] == ".item.id"
        assert (
            InputClassifyingResult.ALL not in mappings
            or not mappings[InputClassifyingResult.ALL]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

        # Test ALL evaluation (contains dots but not pattern)
        mappings = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }
        mocked_processor.group_string_mapping_value(
            "item", mappings, "external_ref", ".external.ref"
        )
        assert mappings[InputClassifyingResult.ALL]["external_ref"] == ".external.ref"
        assert (
            InputClassifyingResult.SINGLE not in mappings
            or not mappings[InputClassifyingResult.SINGLE]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

        # Test NONE evaluation (nullary expression)
        mappings = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }
        mocked_processor.group_string_mapping_value(
            "item", mappings, "static_value", '"static"'
        )
        assert mappings[InputClassifyingResult.NONE]["static_value"] == '"static"'
        assert (
            InputClassifyingResult.SINGLE not in mappings
            or not mappings[InputClassifyingResult.SINGLE]
        )
        assert (
            InputClassifyingResult.ALL not in mappings
            or not mappings[InputClassifyingResult.ALL]
        )

    async def test_group_complex_mapping_value_properties(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with properties dictionary"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test properties with mixed string values
        properties = {
            "name": ".item.name",  # SINGLE
            "description": ".item.desc",  # SINGLE
            "external_ref": ".external.ref",  # ALL
            "static_value": '"static"',  # NONE
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "properties", properties
        )

        expected_single = {
            "name": ".item.name",
            "description": ".item.desc",
        }
        expected_all = {
            "external_ref": ".external.ref",
        }
        expected_none = {
            "static_value": '"static"',
        }

        assert mappings[InputClassifyingResult.SINGLE]["properties"] == expected_single
        assert mappings[InputClassifyingResult.ALL]["properties"] == expected_all
        assert mappings[InputClassifyingResult.NONE]["properties"] == expected_none

    async def test_build_raw_entity_mappings_edge_cases(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test _build_raw_entity_mappings with edge cases including patterns in the middle of expressions"""
        raw_entity_mappings: dict[str, Any] = {
            "identifier": ".item.id",  # Normal case - SINGLE
            "title": "",  # Empty string - NONE
            "blueprint": "   ",  # Whitespace only - NONE
            "icon": ".",  # Just a dot - ALL
            "team": ".item",  # Just the pattern - SINGLE
            "properties": {
                "multiple_patterns": ".item.field.item",  # Multiple occurrences - SINGLE
                "pattern_at_end": ".field.item",  # Pattern at end - ALL (doesn't start with .item)
                "pattern_at_start": ".item.field",  # Pattern at start - SINGLE
                "pattern_in_middle": ".body.somefield.item",  # Pattern in middle - ALL (doesn't start with .item)
                "pattern_in_middle_with_dots": ".data.items.item.field",  # Pattern in middle with dots - ALL
                "case_sensitive": ".ITEM.field",  # Case sensitive (should not match) - ALL
                "special_chars": ".item.field[0]",  # Special characters - SINGLE
                "quoted_pattern": '".item.field"',  # Quoted pattern - NONE
                "field_with_null_name": ".is_null",  # Field with null name - ALL
                "empty_string": "",  # Empty string - NONE
                "item_in_string": 'select(.data.string == ".item")',  # Item referenced in string only - ALL
                "function_with_pattern": "map(.item.field)",  # Function with pattern - SINGLE
                "function_with_middle_pattern": "map(.body.item.field)",  # Function with middle pattern - ALL
                "select_with_pattern": 'select(.item.status == "active")',  # Select with pattern - SINGLE
                "select_with_middle_pattern": 'select(.data.item.status == "active")',  # Select with middle pattern - ALL
                "pipe_with_pattern": ".[] | .item.field",  # Pipe with pattern - SINGLE
                "pipe_with_middle_pattern": ".[] | .body.item.field",  # Pipe with middle pattern - ALL
                "array_with_pattern": "[.item.id, .item.name]",  # Array with pattern - SINGLE
                "array_with_middle_pattern": "[.data.item.id, .body.item.name]",  # Array with middle pattern - ALL
                "object_with_pattern": "{id: .item.id, name: .item.name}",  # Object with pattern - SINGLE
                "object_with_middle_pattern": "{id: .data.item.id, name: .body.item.name}",  # Object with middle pattern - ALL
                "nested_with_pattern": ".data.items[] | .item.field",  # Nested with pattern - SINGLE
                "nested_with_middle_pattern": ".data.items[] | .body.item.field",  # Nested with middle pattern - ALL
                "conditional_with_pattern": "if .item.exists then .item.value else null end",  # Conditional with pattern - SINGLE
                "conditional_with_middle_pattern": "if .data.item.exists then .body.item.value else null end",  # Conditional with middle pattern - ALL
                "string_plus_string": '"abc" + "def"',  # String plus string - NONE
                "number_plus_number": "42 + 10",  # Number plus number - NONE
            },
            "relations": {
                "normal_relation": ".item.owner",  # Normal case - SINGLE
                "middle_pattern_relation": ".data.item.owner",  # Middle pattern - ALL
                "external_relation": ".external.ref",  # External reference - ALL
                "nullary_relation": "null",  # Nullary expression - NONE
            },
        }
        items_to_parse_name = "item"

        single, all_items, none = mocked_processor._build_raw_entity_mappings(
            raw_entity_mappings, items_to_parse_name
        )

        # SINGLE mappings - only those that start with the exact pattern
        expected_single = {
            "identifier": ".item.id",
            "team": ".item",
            "properties": {
                "multiple_patterns": ".item.field.item",
                "pattern_at_start": ".item.field",
                "special_chars": ".item.field[0]",
                "function_with_pattern": "map(.item.field)",
                "select_with_pattern": 'select(.item.status == "active")',
                "pipe_with_pattern": ".[] | .item.field",
                "array_with_pattern": "[.item.id, .item.name]",
                "object_with_pattern": "{id: .item.id, name: .item.name}",
                "nested_with_pattern": ".data.items[] | .item.field",
                "conditional_with_pattern": "if .item.exists then .item.value else null end",
            },
            "relations": {
                "normal_relation": ".item.owner",
            },
        }
        assert single == expected_single

        # ALL mappings - those with dots but not starting with the pattern
        expected_all = {
            "icon": ".",
            "properties": {
                "pattern_at_end": ".field.item",
                "pattern_in_middle": ".body.somefield.item",
                "pattern_in_middle_with_dots": ".data.items.item.field",
                "case_sensitive": ".ITEM.field",
                "function_with_middle_pattern": "map(.body.item.field)",
                "select_with_middle_pattern": 'select(.data.item.status == "active")',
                "item_in_string": 'select(.data.string == ".item")',
                "pipe_with_middle_pattern": ".[] | .body.item.field",
                "array_with_middle_pattern": "[.data.item.id, .body.item.name]",
                "object_with_middle_pattern": "{id: .data.item.id, name: .body.item.name}",
                "nested_with_middle_pattern": ".data.items[] | .body.item.field",
                "conditional_with_middle_pattern": "if .data.item.exists then .body.item.value else null end",
                "field_with_null_name": ".is_null",
            },
            "relations": {
                "middle_pattern_relation": ".data.item.owner",
                "external_relation": ".external.ref",
            },
        }
        assert all_items == expected_all

        # NONE mappings - nullary expressions
        expected_none = {
            "title": "",
            "blueprint": "   ",
            "properties": {
                "quoted_pattern": '".item.field"',
                "empty_string": "",
                "string_plus_string": '"abc" + "def"',
                "number_plus_number": "42 + 10",
            },
            "relations": {
                "nullary_relation": "null",
            },
        }
        assert none == expected_none

    async def test_build_raw_entity_mappings_complex_jq_expressions(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test _build_raw_entity_mappings with complex JQ expressions that contain the pattern but don't start with it"""
        raw_entity_mappings: dict[str, Any] = {
            "identifier": ".item.id",  # Simple case - SINGLE
            "title": ".item.name",  # Simple case - SINGLE
            "blueprint": ".item.type",  # Simple case - SINGLE
            "icon": ".item.icon",  # Simple case - SINGLE
            "team": ".item.team",  # Simple case - SINGLE
            "properties": {
                # JQ expressions with functions that contain .item
                "mapped_property": "map(.item.field)",  # Contains .item but starts with map - SINGLE
                "selected_property": 'select(.item.status == "active")',  # Contains .item but starts with select - SINGLE
                "filtered_property": '.[] | select(.item.type == "service")',  # Contains .item in pipe - SINGLE
                "array_literal": "[.item.id, .item.name]",  # Contains .item in array - SINGLE
                "object_literal": "{id: .item.id, name: .item.name}",  # Contains .item in object - SINGLE
                "nested_access": ".data.items[] | .item.field",  # Contains .item in nested access - SINGLE
                "conditional": "if .item.exists then .item.value else null end",  # Contains .item in conditional - SINGLE
                "function_call": "length(.item.array)",  # Contains .item in function call - SINGLE
                "range_expression": "range(.item.start; .item.end)",  # Contains .item in range - SINGLE
                "reduce_expression": "reduce .item.items[] as $item (0; . + $item.value)",  # Contains .item in reduce - SINGLE
                "group_by": "group_by(.item.category)",  # Contains .item in group_by - SINGLE
                "sort_by": "sort_by(.item.priority)",  # Contains .item in sort_by - SINGLE
                "unique_by": "unique_by(.item.id)",  # Contains .item in unique_by - SINGLE
                "flatten": "flatten(.item.nested)",  # Contains .item in flatten - SINGLE
                "transpose": "transpose(.item.matrix)",  # Contains .item in transpose - SINGLE
                "combinations": "combinations(.item.items)",  # Contains .item in combinations - SINGLE
                "permutations": "permutations(.item.items)",  # Contains .item in permutations - SINGLE
                "bsearch": "bsearch(.item.target)",  # Contains .item in bsearch - SINGLE
                "while_loop": "while(.item.condition; .item.update)",  # Contains .item in while - SINGLE
                "until_loop": "until(.item.condition; .item.update)",  # Contains .item in until - SINGLE
                "recurse": "recurse(.item.children)",  # Contains .item in recurse - SINGLE
                "paths": "paths(.item.structure)",  # Contains .item in paths - SINGLE
                "leaf_paths": "leaf_paths(.item.tree)",  # Contains .item in leaf_paths - SINGLE
                "keys": "keys(.item.object)",  # Contains .item in keys - SINGLE
                "values": "values(.item.object)",  # Contains .item in values - SINGLE
                "to_entries": "to_entries(.item.object)",  # Contains .item in to_entries - SINGLE
                "from_entries": "from_entries(.item.array)",  # Contains .item in from_entries - SINGLE
                "with_entries": "with_entries(.item.transformation)",  # Contains .item in with_entries - SINGLE
                "del": "del(.item.field)",  # Contains .item in del - SINGLE
                "delpaths": "delpaths(.item.paths)",  # Contains .item in delpaths - SINGLE
                "walk": "walk(.item.transformation)",  # Contains .item in walk - SINGLE
                "limit": "limit(.item.count; .item.items)",  # Contains .item in limit - SINGLE
                "first": "first(.item.items)",  # Contains .item in first - SINGLE
                "last": "last(.item.items)",  # Contains .item in last - SINGLE
                "nth": "nth(.item.index; .item.items)",  # Contains .item in nth - SINGLE
                "input": "input(.item.stream)",  # Contains .item in input - SINGLE
                "inputs": "inputs(.item.streams)",  # Contains .item in inputs - SINGLE
                "foreach": "foreach(.item.items) as $item (0; . + $item.value)",  # Contains .item in foreach - SINGLE
                "explode": "explode(.item.string)",  # Contains .item in explode - SINGLE
                "implode": "implode(.item.codes)",  # Contains .item in implode - SINGLE
                "split": "split(.item.delimiter; .item.string)",  # Contains .item in split - SINGLE
                "join": "join(.item.delimiter; .item.array)",  # Contains .item in join - SINGLE
                "add": "add(.item.numbers)",  # Contains .item in add - SINGLE
                "has": "has(.item.key; .item.object)",  # Contains .item in has - SINGLE
                "in": "in(.item.value; .item.array)",  # Contains .item in in - SINGLE
                "index": "index(.item.value; .item.array)",  # Contains .item in index - SINGLE
                "indices": "indices(.item.value; .item.array)",  # Contains .item in indices - SINGLE
                "contains": "contains(.item.value; .item.array)",  # Contains .item in contains - SINGLE
                "startswith": "startswith(.item.prefix; .item.string)",  # Contains .item in startswith - SINGLE
                "endswith": "endswith(.item.suffix; .item.string)",  # Contains .item in endswith - SINGLE
                "ltrimstr": "ltrimstr(.item.prefix; .item.string)",  # Contains .item in ltrimstr - SINGLE
                "rtrimstr": "rtrimstr(.item.suffix; .item.string)",  # Contains .item in rtrimstr - SINGLE
                "sub": "sub(.item.pattern; .item.replacement; .item.string)",  # Contains .item in sub - SINGLE
                "gsub": "gsub(.item.pattern; .item.replacement; .item.string)",  # Contains .item in gsub - SINGLE
                "test": "test(.item.pattern; .item.string)",  # Contains .item in test - SINGLE
                "match": "match(.item.pattern; .item.string)",  # Contains .item in match - SINGLE
                "capture": "capture(.item.pattern; .item.string)",  # Contains .item in capture - SINGLE
                "scan": "scan(.item.pattern; .item.string)",  # Contains .item in scan - SINGLE
                "split_on": "split_on(.item.delimiter; .item.string)",  # Contains .item in split_on - SINGLE
                "join_on": "join_on(.item.delimiter; .item.array)",  # Contains .item in join_on - SINGLE
                "tonumber": "tonumber(.item.string)",  # Contains .item in tonumber - SINGLE
                "tostring": "tostring(.item.number)",  # Contains .item in tostring - SINGLE
                "type": "type(.item.value)",  # Contains .item in type - SINGLE
                "isnan": "isnan(.item.number)",  # Contains .item in isnan - SINGLE
                "isinfinite": "isinfinite(.item.number)",  # Contains .item in isinfinite - SINGLE
                "isfinite": "isfinite(.item.number)",  # Contains .item in isfinite - SINGLE
                "isnormal": "isnormal(.item.number)",  # Contains .item in isnormal - SINGLE
                "floor": "floor(.item.number)",  # Contains .item in floor - SINGLE
                "ceil": "ceil(.item.number)",  # Contains .item in ceil - SINGLE
                "round": "round(.item.number)",  # Contains .item in round - SINGLE
                "sqrt": "sqrt(.item.number)",  # Contains .item in sqrt - SINGLE
                "sin": "sin(.item.angle)",  # Contains .item in sin - SINGLE
                "cos": "cos(.item.angle)",  # Contains .item in cos - SINGLE
                "tan": "tan(.item.angle)",  # Contains .item in tan - SINGLE
                "asin": "asin(.item.value)",  # Contains .item in asin - SINGLE
                "acos": "acos(.item.value)",  # Contains .item in acos - SINGLE
                "atan": "atan(.item.value)",  # Contains .item in atan - SINGLE
                "atan2": "atan2(.item.y; .item.x)",  # Contains .item in atan2 - SINGLE
                "log": "log(.item.number)",  # Contains .item in log - SINGLE
                "log10": "log10(.item.number)",  # Contains .item in log10 - SINGLE
                "log2": "log2(.item.number)",  # Contains .item in log2 - SINGLE
                "exp": "exp(.item.number)",  # Contains .item in exp - SINGLE
                "exp10": "exp10(.item.number)",  # Contains .item in exp10 - SINGLE
                "exp2": "exp2(.item.number)",  # Contains .item in exp2 - SINGLE
                "pow": "pow(.item.base; .item.exponent)",  # Contains .item in pow - SINGLE
                "fma": "fma(.item.x; .item.y; .item.z)",  # Contains .item in fma - SINGLE
                "fmod": "fmod(.item.x; .item.y)",  # Contains .item in fmod - SINGLE
                "remainder": "remainder(.item.x; .item.y)",  # Contains .item in remainder - SINGLE
                "drem": "drem(.item.x; .item.y)",  # Contains .item in drem - SINGLE
                "fabs": "fabs(.item.number)",  # Contains .item in fabs - SINGLE
                "fmax": "fmax(.item.x; .item.y)",  # Contains .item in fmax - SINGLE
                "fmin": "fmin(.item.x; .item.y)",  # Contains .item in fmin - SINGLE
                "fdim": "fdim(.item.x; .item.y)",  # Contains .item in fdim - SINGLE
                # Expressions that don't contain .item (should go to ALL or NONE)
                "external_map": "map(.external.field)",  # Doesn't contain .item - ALL
                "external_select": 'select(.external.status == "active")',  # Doesn't contain .item - ALL
                "external_array": "[.external.id, .external.name]",  # Doesn't contain .item - ALL
                "static_value": '"static"',  # Static value - NONE
                "nullary_expression": "null",  # Nullary expression - NONE
                "boolean_expression": "true",  # Boolean expression - NONE
                "number_expression": "42",  # Number expression - NONE
                "string_expression": '"hello"',  # String expression - NONE
                "array_expression": "[1,2,3]",  # Array expression - NONE
                "object_expression": '{"key": "value"}',  # Object expression - NONE
            },
            "relations": {
                "mapped_relation": "map(.item.relation)",  # Contains .item - SINGLE
                "selected_relation": 'select(.item.relation == "active")',  # Contains .item - SINGLE
                "external_relation": "map(.external.relation)",  # Doesn't contain .item - ALL
                "static_relation": '"static"',  # Static value - NONE
            },
        }
        items_to_parse_name = "item"

        single, all_items, none = mocked_processor._build_raw_entity_mappings(
            raw_entity_mappings, items_to_parse_name
        )

        # SINGLE mappings - all expressions that contain .item
        expected_single = {
            "identifier": ".item.id",
            "title": ".item.name",
            "blueprint": ".item.type",
            "icon": ".item.icon",
            "team": ".item.team",
            "properties": {
                "mapped_property": "map(.item.field)",
                "selected_property": 'select(.item.status == "active")',
                "filtered_property": '.[] | select(.item.type == "service")',
                "array_literal": "[.item.id, .item.name]",
                "object_literal": "{id: .item.id, name: .item.name}",
                "nested_access": ".data.items[] | .item.field",
                "conditional": "if .item.exists then .item.value else null end",
                "function_call": "length(.item.array)",
                "range_expression": "range(.item.start; .item.end)",
                "reduce_expression": "reduce .item.items[] as $item (0; . + $item.value)",
                "group_by": "group_by(.item.category)",
                "sort_by": "sort_by(.item.priority)",
                "unique_by": "unique_by(.item.id)",
                "flatten": "flatten(.item.nested)",
                "transpose": "transpose(.item.matrix)",
                "combinations": "combinations(.item.items)",
                "permutations": "permutations(.item.items)",
                "bsearch": "bsearch(.item.target)",
                "while_loop": "while(.item.condition; .item.update)",
                "until_loop": "until(.item.condition; .item.update)",
                "recurse": "recurse(.item.children)",
                "paths": "paths(.item.structure)",
                "leaf_paths": "leaf_paths(.item.tree)",
                "keys": "keys(.item.object)",
                "values": "values(.item.object)",
                "to_entries": "to_entries(.item.object)",
                "from_entries": "from_entries(.item.array)",
                "with_entries": "with_entries(.item.transformation)",
                "del": "del(.item.field)",
                "delpaths": "delpaths(.item.paths)",
                "walk": "walk(.item.transformation)",
                "limit": "limit(.item.count; .item.items)",
                "first": "first(.item.items)",
                "last": "last(.item.items)",
                "nth": "nth(.item.index; .item.items)",
                "input": "input(.item.stream)",
                "inputs": "inputs(.item.streams)",
                "foreach": "foreach(.item.items) as $item (0; . + $item.value)",
                "explode": "explode(.item.string)",
                "implode": "implode(.item.codes)",
                "split": "split(.item.delimiter; .item.string)",
                "join": "join(.item.delimiter; .item.array)",
                "add": "add(.item.numbers)",
                "has": "has(.item.key; .item.object)",
                "in": "in(.item.value; .item.array)",
                "index": "index(.item.value; .item.array)",
                "indices": "indices(.item.value; .item.array)",
                "contains": "contains(.item.value; .item.array)",
                "startswith": "startswith(.item.prefix; .item.string)",
                "endswith": "endswith(.item.suffix; .item.string)",
                "ltrimstr": "ltrimstr(.item.prefix; .item.string)",
                "rtrimstr": "rtrimstr(.item.suffix; .item.string)",
                "sub": "sub(.item.pattern; .item.replacement; .item.string)",
                "gsub": "gsub(.item.pattern; .item.replacement; .item.string)",
                "test": "test(.item.pattern; .item.string)",
                "match": "match(.item.pattern; .item.string)",
                "capture": "capture(.item.pattern; .item.string)",
                "scan": "scan(.item.pattern; .item.string)",
                "split_on": "split_on(.item.delimiter; .item.string)",
                "join_on": "join_on(.item.delimiter; .item.array)",
                "tonumber": "tonumber(.item.string)",
                "tostring": "tostring(.item.number)",
                "type": "type(.item.value)",
                "isnan": "isnan(.item.number)",
                "isinfinite": "isinfinite(.item.number)",
                "isfinite": "isfinite(.item.number)",
                "isnormal": "isnormal(.item.number)",
                "floor": "floor(.item.number)",
                "ceil": "ceil(.item.number)",
                "round": "round(.item.number)",
                "sqrt": "sqrt(.item.number)",
                "sin": "sin(.item.angle)",
                "cos": "cos(.item.angle)",
                "tan": "tan(.item.angle)",
                "asin": "asin(.item.value)",
                "acos": "acos(.item.value)",
                "atan": "atan(.item.value)",
                "atan2": "atan2(.item.y; .item.x)",
                "log": "log(.item.number)",
                "log10": "log10(.item.number)",
                "log2": "log2(.item.number)",
                "exp": "exp(.item.number)",
                "exp10": "exp10(.item.number)",
                "exp2": "exp2(.item.number)",
                "pow": "pow(.item.base; .item.exponent)",
                "fma": "fma(.item.x; .item.y; .item.z)",
                "fmod": "fmod(.item.x; .item.y)",
                "remainder": "remainder(.item.x; .item.y)",
                "drem": "drem(.item.x; .item.y)",
                "fabs": "fabs(.item.number)",
                "fmax": "fmax(.item.x; .item.y)",
                "fmin": "fmin(.item.x; .item.y)",
                "fdim": "fdim(.item.x; .item.y)",
            },
            "relations": {
                "mapped_relation": "map(.item.relation)",
                "selected_relation": 'select(.item.relation == "active")',
            },
        }
        assert single == expected_single

        # ALL mappings - expressions with dots but not containing .item
        expected_all = {
            "properties": {
                "external_map": "map(.external.field)",
                "external_select": 'select(.external.status == "active")',
                "external_array": "[.external.id, .external.name]",
            },
            "relations": {
                "external_relation": "map(.external.relation)",
            },
        }
        assert all_items == expected_all

        # NONE mappings - nullary expressions and static values
        expected_none = {
            "properties": {
                "static_value": '"static"',
                "nullary_expression": "null",
                "boolean_expression": "true",
                "number_expression": "42",
                "string_expression": '"hello"',
                "array_expression": "[1,2,3]",
                "object_expression": '{"key": "value"}',
            },
            "relations": {
                "static_relation": '"static"',
            },
        }
        assert none == expected_none

    async def test_group_complex_mapping_value_relations(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with relations dictionary"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test relations with mixed string and IngestSearchQuery values
        relations = {
            "owner": ".item.owner",  # String - SINGLE
            "parent": {  # IngestSearchQuery - SINGLE
                "combinator": "and",
                "rules": [
                    {
                        "property": "parent",
                        "operator": "equals",
                        "value": ".item.parent",
                    }
                ],
            },
            "external_relation": {  # IngestSearchQuery - ALL
                "combinator": "and",
                "rules": [
                    {
                        "property": "external",
                        "operator": "equals",
                        "value": ".external.ref",
                    }
                ],
            },
            "static_relation": '"static"',  # String - NONE
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "relations", relations
        )

        expected_single = {
            "owner": ".item.owner",
            "parent": {
                "combinator": "and",
                "rules": [
                    {
                        "property": "parent",
                        "operator": "equals",
                        "value": ".item.parent",
                    }
                ],
            },
        }
        expected_all = {
            "external_relation": {
                "combinator": "and",
                "rules": [
                    {
                        "property": "external",
                        "operator": "equals",
                        "value": ".external.ref",
                    }
                ],
            }
        }
        expected_none = {
            "static_relation": '"static"',
        }

        assert mappings[InputClassifyingResult.SINGLE]["relations"] == expected_single
        assert mappings[InputClassifyingResult.ALL]["relations"] == expected_all
        assert mappings[InputClassifyingResult.NONE]["relations"] == expected_none

    async def test_group_complex_mapping_value_identifier_ingest_search_query(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with identifier IngestSearchQuery"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test identifier IngestSearchQuery that matches pattern
        identifier_query = {
            "combinator": "and",
            "rules": [{"property": "id", "operator": "equals", "value": ".item.id"}],
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "identifier", identifier_query
        )

        expected_single = {
            "combinator": "and",
            "rules": [{"property": "id", "operator": "equals", "value": ".item.id"}],
        }

        assert mappings[InputClassifyingResult.SINGLE]["identifier"] == expected_single
        assert (
            InputClassifyingResult.ALL not in mappings
            or not mappings[InputClassifyingResult.ALL]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

    async def test_group_complex_mapping_value_team_ingest_search_query(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with team IngestSearchQuery"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test team IngestSearchQuery that doesn't match pattern
        team_query = {
            "combinator": "and",
            "rules": [
                {"property": "team", "operator": "equals", "value": ".data.team"}
            ],
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "team", team_query
        )

        expected_all = {
            "combinator": "and",
            "rules": [
                {"property": "team", "operator": "equals", "value": ".data.team"}
            ],
        }

        assert mappings[InputClassifyingResult.ALL]["team"] == expected_all
        assert (
            InputClassifyingResult.SINGLE not in mappings
            or not mappings[InputClassifyingResult.SINGLE]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

    async def test_group_complex_mapping_value_nested_ingest_search_query(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with nested IngestSearchQuery"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test nested IngestSearchQuery with mixed rules
        nested_query = {
            "combinator": "and",
            "rules": [
                {
                    "property": "field",
                    "operator": "equals",
                    "value": ".item.field",  # SINGLE - contains pattern
                },
                {
                    "combinator": "or",
                    "rules": [
                        {
                            "property": "external",
                            "operator": "equals",
                            "value": ".external.ref",  # ALL - doesn't contain pattern
                        }
                    ],
                },
            ],
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "identifier", nested_query
        )

        # Should go to SINGLE because it contains at least one rule with the pattern
        expected_single = {
            "combinator": "and",
            "rules": [
                {"property": "field", "operator": "equals", "value": ".item.field"},
                {
                    "combinator": "or",
                    "rules": [
                        {
                            "property": "external",
                            "operator": "equals",
                            "value": ".external.ref",
                        }
                    ],
                },
            ],
        }

        assert mappings[InputClassifyingResult.SINGLE]["identifier"] == expected_single
        assert (
            InputClassifyingResult.ALL not in mappings
            or not mappings[InputClassifyingResult.ALL]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

    async def test_group_complex_mapping_value_invalid_ingest_search_query(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with invalid IngestSearchQuery structures"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test invalid IngestSearchQuery (no rules field)
        invalid_query = {
            "combinator": "and"
            # Missing rules field
        }

        mocked_processor.group_complex_mapping_value(
            ".item", mappings, "identifier", invalid_query
        )

        # Should go to ALL since it doesn't match the pattern
        expected_all = {"combinator": "and"}

        assert mappings[InputClassifyingResult.ALL]["identifier"] == expected_all
        assert (
            InputClassifyingResult.SINGLE not in mappings
            or not mappings[InputClassifyingResult.SINGLE]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

    async def test_group_complex_mapping_value_empty_dict(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with empty dictionary"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test empty properties dictionary
        empty_properties: dict[str, Any] = {}

        mocked_processor.group_complex_mapping_value(
            ".item", mappings, "properties", empty_properties
        )

        # Should not add anything to any mapping
        assert (
            InputClassifyingResult.SINGLE not in mappings
            or not mappings[InputClassifyingResult.SINGLE]
        )
        assert (
            InputClassifyingResult.ALL not in mappings
            or not mappings[InputClassifyingResult.ALL]
        )
        assert (
            InputClassifyingResult.NONE not in mappings
            or not mappings[InputClassifyingResult.NONE]
        )

    async def test_group_complex_mapping_value_mixed_content(
        self, mocked_processor: JQEntityProcessor
    ) -> None:
        """Test group_complex_mapping_value with mixed string and IngestSearchQuery content"""
        from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
            InputClassifyingResult,
        )

        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
            InputClassifyingResult.NONE: {},
        }

        # Test properties with mixed content
        mixed_properties = {
            "string_single": ".item.name",  # String - SINGLE
            "string_all": ".external.ref",  # String - ALL
            "string_none": '"static"',  # String - NONE
            "query_single": {  # IngestSearchQuery - SINGLE
                "combinator": "and",
                "rules": [
                    {"property": "field", "operator": "equals", "value": ".item.field"}
                ],
            },
            "query_all": {  # IngestSearchQuery - ALL
                "combinator": "and",
                "rules": [
                    {
                        "property": "external",
                        "operator": "equals",
                        "value": ".external.field",
                    }
                ],
            },
        }

        mocked_processor.group_complex_mapping_value(
            "item", mappings, "properties", mixed_properties
        )

        expected_single = {
            "string_single": ".item.name",
            "query_single": {
                "combinator": "and",
                "rules": [
                    {"property": "field", "operator": "equals", "value": ".item.field"}
                ],
            },
        }
        expected_all = {
            "string_all": ".external.ref",
            "query_all": {
                "combinator": "and",
                "rules": [
                    {
                        "property": "external",
                        "operator": "equals",
                        "value": ".external.field",
                    }
                ],
            },
        }
        expected_none = {
            "string_none": '"static"',
        }

        assert mappings[InputClassifyingResult.SINGLE]["properties"] == expected_single
        assert mappings[InputClassifyingResult.ALL]["properties"] == expected_all
        assert mappings[InputClassifyingResult.NONE]["properties"] == expected_none
