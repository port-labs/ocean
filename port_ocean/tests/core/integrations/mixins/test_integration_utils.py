import pytest

from port_ocean.core.integrations.mixins.utils import (
    _build_mapping_jq_expression,
    extract_jq_deletion_path_revised,
    recursive_dict_merge,
)


class TestBuildMappingJqExpression:
    """Tests for _build_mapping_jq_expression function."""

    def test_build_mapping_jq_expression_non_path_type(self) -> None:
        """Test jq expression building for non-path type."""
        items_to_parse_name = "items"
        base_jq = ".file.content"
        delete_target = ".file.content.raw"

        result = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=False
        )

        expected = "map(($all | del(.file.content.raw)) + {items: . })"
        assert result == expected

    def test_build_mapping_jq_expression_path_type(self) -> None:
        """Test jq expression building for path type."""
        items_to_parse_name = "items"
        base_jq = ".file.content"
        delete_target = ".file.content.raw"

        result = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=True
        )

        expected = "map({items: . } | .file.content = (($all | del(.file.content.raw)) // {}))"
        assert result == expected

    def test_build_mapping_jq_expression_with_different_delete_target(self) -> None:
        """Test jq expression building with different delete targets."""
        items_to_parse_name = "parsed_data"
        base_jq = ".data"
        delete_target = ".data.temp"

        # Non-path type
        result_non_path = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=False
        )
        expected_non_path = "map(($all | del(.data.temp)) + {parsed_data: . })"
        assert result_non_path == expected_non_path

        # Path type
        result_path = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=True
        )
        expected_path = "map({parsed_data: . } | .data = (($all | del(.data.temp)) // {}))"
        assert result_path == expected_path

    def test_build_mapping_jq_expression_with_simple_delete_target(self) -> None:
        """Test jq expression building with simple delete target."""
        items_to_parse_name = "items"
        base_jq = "."
        delete_target = "."

        # Non-path type
        result_non_path = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=False
        )
        expected_non_path = "map(($all | del(.)) + {items: . })"
        assert result_non_path == expected_non_path

        # Path type
        result_path = _build_mapping_jq_expression(
            items_to_parse_name, base_jq, delete_target, is_path_type=True
        )
        expected_path = "map({items: . } | . = (($all | del(.)) // {}))"
        assert result_path == expected_path


class TestRecursiveDictMerge:
    """Tests for recursive_dict_merge function."""

    def test_simple_merge_new_keys(self) -> None:
        """Test merging dictionaries with new keys."""
        d1 = {"a": 1, "b": 2}
        d2 = {"c": 3, "d": 4}

        result = recursive_dict_merge(d1, d2)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}
        # Ensure original dicts are not modified
        assert d1 == {"a": 1, "b": 2}
        assert d2 == {"c": 3, "d": 4}

    def test_simple_overwrite(self) -> None:
        """Test overwriting values with non-dict values."""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 3, "c": 4}

        result = recursive_dict_merge(d1, d2)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge(self) -> None:
        """Test recursive merging of nested dictionaries."""
        d1 = {"a": 1, "nested": {"x": 10, "y": 20}}
        d2 = {"b": 2, "nested": {"y": 30, "z": 40}}

        result = recursive_dict_merge(d1, d2)

        assert result == {"a": 1, "b": 2, "nested": {"x": 10, "y": 30, "z": 40}}

    def test_empty_dict_overwrite(self) -> None:
        """Test that empty dict in d2 overwrites non-empty dict in d1."""
        d1 = {"a": 1, "nested": {"x": 10, "y": 20}}
        d2 = {"nested": {}}

        result = recursive_dict_merge(d1, d2)

        assert result == {"a": 1, "nested": {}}

    def test_empty_dict_overwrite_multiple_levels(self) -> None:
        """Test empty dict overwrite at multiple nesting levels."""
        d1 = {
            "level1": {
                "level2": {
                    "level3": {"value": 100}
                }
            }
        }
        d2 = {
            "level1": {
                "level2": {}
            }
        }

        result = recursive_dict_merge(d1, d2)

        assert result == {"level1": {"level2": {}}}

    def test_mixed_types(self) -> None:
        """Test merging with mixed value types."""
        d1 = {
            "string": "hello",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"a": 1}
        }
        d2 = {
            "string": "world",
            "number": 100,
            "list": [4, 5, 6],
            "nested": {"b": 2}
        }

        result = recursive_dict_merge(d1, d2)

        assert result == {
            "string": "world",
            "number": 100,
            "list": [4, 5, 6],
            "nested": {"a": 1, "b": 2}
        }

    def test_deep_nested_merge(self) -> None:
        """Test merging deeply nested structures."""
        d1 = {
            "a": {
                "b": {
                    "c": {
                        "d": 1,
                        "e": 2
                    }
                }
            }
        }
        d2 = {
            "a": {
                "b": {
                    "c": {
                        "e": 3,
                        "f": 4
                    }
                }
            }
        }

        result = recursive_dict_merge(d1, d2)

        assert result == {
            "a": {
                "b": {
                    "c": {
                        "d": 1,
                        "e": 3,
                        "f": 4
                    }
                }
            }
        }

    def test_empty_dictionaries(self) -> None:
        """Test merging with empty dictionaries."""
        d1 = {}
        d2 = {"a": 1}

        result = recursive_dict_merge(d1, d2)

        assert result == {"a": 1}

    def test_both_empty_dictionaries(self) -> None:
        """Test merging two empty dictionaries."""
        d1 = {}
        d2 = {}

        result = recursive_dict_merge(d1, d2)

        assert result == {}

    def test_immutability_d1(self) -> None:
        """Test that d1 is not modified by the merge operation."""
        d1 = {"a": 1, "nested": {"x": 10}}
        d2 = {"b": 2, "nested": {"y": 20}}

        original_d1 = {"a": 1, "nested": {"x": 10}}
        result = recursive_dict_merge(d1, d2)

        # Verify d1 is unchanged
        assert d1 == original_d1
        # Verify result is correct
        assert result == {"a": 1, "b": 2, "nested": {"x": 10, "y": 20}}

    def test_immutability_d2(self) -> None:
        """Test that d2 is not modified by the merge operation."""
        d1 = {"a": 1}
        d2 = {"b": 2, "nested": {"x": 10}}

        original_d2 = {"b": 2, "nested": {"x": 10}}
        result = recursive_dict_merge(d1, d2)

        # Verify d2 is unchanged
        assert d2 == original_d2
        # Verify result is correct
        assert result == {"a": 1, "b": 2, "nested": {"x": 10}}

    def test_non_dict_value_overwrites_dict(self) -> None:
        """Test that non-dict value in d2 overwrites dict value in d1."""
        d1 = {"key": {"nested": "value"}}
        d2 = {"key": "simple_string"}

        result = recursive_dict_merge(d1, d2)

        assert result == {"key": "simple_string"}

    def test_dict_overwrites_non_dict_value(self) -> None:
        """Test that dict value in d2 overwrites non-dict value in d1."""
        d1 = {"key": "simple_string"}
        d2 = {"key": {"nested": "value"}}

        result = recursive_dict_merge(d1, d2)

        assert result == {"key": {"nested": "value"}}

    def test_complex_real_world_scenario(self) -> None:
        """Test a complex real-world merge scenario."""
        d1 = {
            "metadata": {
                "version": "1.0",
                "author": "Alice",
                "tags": ["python", "testing"]
            },
            "data": {
                "users": {
                    "count": 100,
                    "active": 80
                }
            },
            "config": {
                "debug": False
            }
        }
        d2 = {
            "metadata": {
                "version": "2.0",
                "tags": ["python", "testing", "advanced"]
            },
            "data": {
                "users": {
                    "active": 90
                },
                "posts": {
                    "count": 200
                }
            },
            "config": {}
        }

        result = recursive_dict_merge(d1, d2)

        assert result == {
            "metadata": {
                "version": "2.0",
                "author": "Alice",
                "tags": ["python", "testing", "advanced"]
            },
            "data": {
                "users": {
                    "count": 100,
                    "active": 90
                },
                "posts": {
                    "count": 200
                }
            },
            "config": {}
        }


class TestExtractJqDeletionPathRevised:
    """Tests for extract_jq_deletion_path_revised function."""

    def test_simple_path(self) -> None:
        """Test extraction of simple path like .key."""
        result = extract_jq_deletion_path_revised(".file.content")
        assert result == ".file.content"

    def test_simple_single_key(self) -> None:
        """Test extraction of single key path."""
        result = extract_jq_deletion_path_revised(".key")
        assert result == ".key"

    def test_nested_path(self) -> None:
        """Test extraction of nested path."""
        result = extract_jq_deletion_path_revised(".file.content.raw")
        assert result == ".file.content.raw"

    def test_path_with_parentheses(self) -> None:
        """Test extraction with surrounding parentheses."""
        result = extract_jq_deletion_path_revised("(.file.content)")
        assert result == ".file.content"

    def test_path_with_pipe_segments(self) -> None:
        """Test extraction from pipe-separated expression."""
        result = extract_jq_deletion_path_revised(". as $all | .file.content")
        assert result == ".file.content"

    def test_path_with_variable_assignment_ignored(self) -> None:
        """Test that variable assignment segments are ignored."""
        result = extract_jq_deletion_path_revised(". as $root | .file.content")
        assert result == ".file.content"

    def test_path_with_variable_access_ignored(self) -> None:
        """Test that variable access like $items is ignored."""
        result = extract_jq_deletion_path_revised("$items | .file.content")
        assert result == ".file.content"

    def test_identity_operator_ignored(self) -> None:
        """Test that identity operator '.' is ignored."""
        result = extract_jq_deletion_path_revised(". | .file.content")
        assert result == ".file.content"

    def test_path_with_fallback_operator(self) -> None:
        """Test path extraction with fallback operator (//)."""
        result = extract_jq_deletion_path_revised(".file.content // {}")
        assert result == ".file.content"

    def test_path_with_fallback_to_null(self) -> None:
        """Test path extraction with fallback to null."""
        result = extract_jq_deletion_path_revised(".file.content // null")
        assert result == ".file.content"

    def test_path_with_fallback_to_empty_array(self) -> None:
        """Test path extraction with fallback to empty array."""
        result = extract_jq_deletion_path_revised(".file.content // []")
        assert result == ".file.content"

    def test_path_with_fallback_to_object(self) -> None:
        """Test path extraction with fallback to object."""
        result = extract_jq_deletion_path_revised(".file.content // {}")
        assert result == ".file.content"

    def test_path_with_bracketed_accessor(self) -> None:
        """Test path extraction with array index accessor."""
        result = extract_jq_deletion_path_revised(".[0].key")
        assert result == ".[0].key"

    def test_path_with_multiple_bracketed_accessors(self) -> None:
        """Test path extraction with multiple array index accessors."""
        result = extract_jq_deletion_path_revised(".[0].[1].key")
        assert result == ".[0].[1].key"

    def test_path_with_mixed_accessors(self) -> None:
        """Test path extraction with mixed key and bracket accessors."""
        result = extract_jq_deletion_path_revised(".file[0].content")
        assert result == ".file[0].content"

    def test_path_with_mixed_accessors_with_dots(self) -> None:
        """Test path extraction with mixed key and bracket accessors with dots."""
        result = extract_jq_deletion_path_revised(".file.[0].content")
        assert result == ".file.[0].content"

    def test_complex_pipe_expression(self) -> None:
        """Test extraction from complex pipe expression."""
        result = extract_jq_deletion_path_revised(
            ". as $all | ($all | .file.content) as $items | $items"
        )
        assert result == ".file.content"

    def test_path_in_parentheses_with_pipes(self) -> None:
        """Test path extraction from parenthesized expression with pipes."""
        result = extract_jq_deletion_path_revised("(. as $all | .file.content)")
        assert result == ".file.content"

    def test_no_path_returns_none(self) -> None:
        """Test that expression without path returns None."""
        result = extract_jq_deletion_path_revised("$items")
        assert result is None

    def test_only_identity_returns_none(self) -> None:
        """Test that expression with only identity operator returns None."""
        result = extract_jq_deletion_path_revised(".")
        assert result is None

    def test_only_variable_returns_none(self) -> None:
        """Test that expression with only variable returns None."""
        result = extract_jq_deletion_path_revised("$items")
        assert result is None

    def test_only_variable_assignment_returns_none(self) -> None:
        """Test that expression with only variable assignment returns None."""
        result = extract_jq_deletion_path_revised(". as $root")
        assert result is None

    def test_malformed_parentheses_returns_none(self) -> None:
        """Test that malformed parentheses return None."""
        result = extract_jq_deletion_path_revised("(.file.content")
        assert result is None

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly handled."""
        result = extract_jq_deletion_path_revised("  .file.content  ")
        assert result == ".file.content"

    def test_path_with_underscores(self) -> None:
        """Test path extraction with underscores in keys."""
        result = extract_jq_deletion_path_revised(".file_content.raw_data")
        assert result == ".file_content.raw_data"

    def test_path_with_numbers_in_keys(self) -> None:
        """Test path extraction with numbers in keys."""
        result = extract_jq_deletion_path_revised(".file2.content3")
        assert result == ".file2.content3"

    def test_deeply_nested_path(self) -> None:
        """Test extraction of deeply nested path."""
        result = extract_jq_deletion_path_revised(".a.b.c.d.e.f")
        assert result == ".a.b.c.d.e.f"

    def test_path_with_fallback_in_pipe(self) -> None:
        """Test path extraction with fallback in pipe expression."""
        result = extract_jq_deletion_path_revised(". as $all | .file.content // {}")
        assert result == ".file.content"

    def test_multiple_paths_returns_first(self) -> None:
        """Test that first valid path is returned when multiple exist."""
        result = extract_jq_deletion_path_revised(".first.path | .second.path")
        assert result == ".first.path"

    def test_path_with_complex_bracket_expression(self) -> None:
        """Test path extraction with complex bracket expression."""
        result = extract_jq_deletion_path_revised(".[\"key\"].value")
        assert result == ".[\"key\"].value"

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        result = extract_jq_deletion_path_revised("")
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string returns None."""
        result = extract_jq_deletion_path_revised("   ")
        assert result is None

    def test_real_world_file_content_path(self) -> None:
        """Test real-world scenario: file.content path."""
        result = extract_jq_deletion_path_revised(".file.content.raw")
        assert result == ".file.content.raw"

    def test_real_world_with_variable_and_fallback(self) -> None:
        """Test real-world scenario with variable and fallback."""
        result = extract_jq_deletion_path_revised(
            ". as $all | ($all | .file.content.raw) // {}"
        )
        assert result == ".file.content.raw"
