from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
    InputClassifyingResult,
    can_expression_run_with_no_input,
    _can_expression_run_on_single_item,
    classify_input,
    _mask_strings,
    _mask_numbers,
)


class TestMaskStrings:
    """Test the _mask_strings function"""

    def test_mask_simple_string(self) -> None:
        """Test masking a simple string literal"""
        expr = '"hello world"'
        result = _mask_strings(expr)
        assert result == "S"

    def test_mask_string_with_escaped_quotes(self) -> None:
        """Test masking a string with escaped quotes"""
        expr = '"hello \\"world\\""'
        result = _mask_strings(expr)
        assert result == "S"

    def test_mask_string_with_backslash(self) -> None:
        """Test masking a string with backslash"""
        expr = '"hello\\\\world"'
        result = _mask_strings(expr)
        assert result == "S"

    def test_mask_multiple_strings(self) -> None:
        """Test masking multiple string literals"""
        expr = '"hello" + "world"'
        result = _mask_strings(expr)
        assert result == "S + S"

    def test_mask_string_with_dots_inside(self) -> None:
        """Test masking a string that contains dots (should not affect dot detection)"""
        expr = '"this.is.a.string" + .field'
        result = _mask_strings(expr)
        assert result == "S + .field"

    def test_mask_empty_string(self) -> None:
        """Test masking an empty string"""
        expr = '""'
        result = _mask_strings(expr)
        assert result == "S"

    def test_no_strings_to_mask(self) -> None:
        """Test expression with no strings"""
        expr = ".field + .other"
        result = _mask_strings(expr)
        assert result == ".field + .other"

    def test_mixed_content(self) -> None:
        """Test masking with mixed content"""
        expr = '"hello" + .field + "world"'
        result = _mask_strings(expr)
        assert result == "S + .field + S"


class TestMaskNumbers:
    """Test the _mask_numbers function"""

    def test_mask_simple_number(self) -> None:
        """Test masking a simple number"""
        expr = "42"
        result = _mask_numbers(expr)
        assert result == "N"

    def test_mask_decimal_number(self) -> None:
        """Test masking a decimal number"""
        expr = "3.14"
        result = _mask_numbers(expr)
        assert result == "N"

    def test_mask_negative_number(self) -> None:
        """Test masking a negative number"""
        expr = "-42"
        result = _mask_numbers(expr)
        assert result == "N"

    def test_mask_negative_decimal(self) -> None:
        """Test masking a negative decimal"""
        expr = "-3.14"
        result = _mask_numbers(expr)
        assert result == "N"

    def test_mask_positive_number_with_sign(self) -> None:
        """Test masking a positive number with explicit sign"""
        expr = "+42"
        result = _mask_numbers(expr)
        assert result == "N"

    def test_mask_multiple_numbers(self) -> None:
        """Test masking multiple numbers"""
        expr = "3.14 + 2.5"
        result = _mask_numbers(expr)
        assert result == "N + N"

    def test_mask_numbers_with_operators(self) -> None:
        """Test masking numbers with various operators"""
        expr = "3.14 * 2.5 - 1.5 / 2"
        result = _mask_numbers(expr)
        assert result == "N * N - N / N"

    def test_mask_numbers_with_strings(self) -> None:
        """Test masking numbers mixed with strings (should not affect strings)"""
        expr = '"hello" + 3.14 + "world"'
        result = _mask_numbers(expr)
        assert result == '"hello" + N + "world"'

    def test_mask_numbers_with_field_references(self) -> None:
        """Test masking numbers with field references (should not affect field references)"""
        expr = "3.14 + .field"
        result = _mask_numbers(expr)
        assert result == "N + .field"

    def test_no_numbers_to_mask(self) -> None:
        """Test expression with no numbers"""
        expr = ".field + .other"
        result = _mask_numbers(expr)
        assert result == ".field + .other"

    def test_mixed_content_with_numbers(self) -> None:
        """Test masking with mixed content including numbers"""
        expr = '"hello" + 3.14 + .field + 42'
        result = _mask_numbers(expr)
        assert result == '"hello" + N + .field + N'


class TestCanExpressionRunWithNoInput:
    """Test the can_expression_run_with_no_input function"""

    def test_empty_string(self) -> None:
        """Test empty string returns True"""
        assert can_expression_run_with_no_input("") is True
        assert can_expression_run_with_no_input("   ") is True

    def test_pure_string_literal(self) -> None:
        """Test pure string literals return True"""
        assert can_expression_run_with_no_input('"hello"') is True
        assert can_expression_run_with_no_input('"hello world"') is True
        assert can_expression_run_with_no_input('"hello\\"world"') is True
        assert can_expression_run_with_no_input('"this.is.a.string"') is True

    def test_string_with_dots_inside(self) -> None:
        """Test string literals with dots inside return True"""
        assert can_expression_run_with_no_input('"this.is.a.string"') is True
        assert can_expression_run_with_no_input('"path/to/file"') is True

    def test_contains_dots_outside_strings(self) -> None:
        """Test expressions with dots outside strings return False"""
        assert can_expression_run_with_no_input(".field") is False
        assert can_expression_run_with_no_input('"hello" + .field') is False
        assert can_expression_run_with_no_input('.field + "world"') is False

    def test_input_dependent_functions(self) -> None:
        """Test expressions with input-dependent functions return False"""
        assert can_expression_run_with_no_input("map(.field)") is False
        assert can_expression_run_with_no_input("select(.field)") is False
        assert can_expression_run_with_no_input("length(.field)") is False
        assert can_expression_run_with_no_input("keys(.field)") is False
        assert can_expression_run_with_no_input("values(.field)") is False
        assert can_expression_run_with_no_input("has(.field)") is False
        assert can_expression_run_with_no_input("in(.field)") is False
        assert can_expression_run_with_no_input("index(.field)") is False
        assert can_expression_run_with_no_input("indices(.field)") is False
        assert can_expression_run_with_no_input("contains(.field)") is False
        assert can_expression_run_with_no_input("paths(.field)") is False
        assert can_expression_run_with_no_input("leaf_paths(.field)") is False
        assert can_expression_run_with_no_input("to_entries(.field)") is False
        assert can_expression_run_with_no_input("from_entries(.field)") is False
        assert can_expression_run_with_no_input("with_entries(.field)") is False
        assert can_expression_run_with_no_input("del(.field)") is False
        assert can_expression_run_with_no_input("delpaths(.field)") is False
        assert can_expression_run_with_no_input("walk(.field)") is False
        assert can_expression_run_with_no_input("reduce(.field)") is False
        assert can_expression_run_with_no_input("foreach(.field)") is False
        assert can_expression_run_with_no_input("input(.field)") is False
        assert can_expression_run_with_no_input("inputs(.field)") is False
        assert can_expression_run_with_no_input("limit(.field)") is False
        assert can_expression_run_with_no_input("first(.field)") is False
        assert can_expression_run_with_no_input("last(.field)") is False
        assert can_expression_run_with_no_input("nth(.field)") is False
        assert can_expression_run_with_no_input("while(.field)") is False
        assert can_expression_run_with_no_input("until(.field)") is False
        assert can_expression_run_with_no_input("recurse(.field)") is False
        assert can_expression_run_with_no_input("recurse_down(.field)") is False
        assert can_expression_run_with_no_input("bsearch(.field)") is False
        assert can_expression_run_with_no_input("combinations(.field)") is False
        assert can_expression_run_with_no_input("permutations(.field)") is False

    def test_nullary_expressions(self) -> None:
        """Test nullary expressions return True"""
        assert can_expression_run_with_no_input("null") is True
        assert can_expression_run_with_no_input("true") is True
        assert can_expression_run_with_no_input("false") is True
        assert can_expression_run_with_no_input("42") is True
        assert can_expression_run_with_no_input("-42") is True
        assert can_expression_run_with_no_input("3.14") is True
        assert can_expression_run_with_no_input("-3.14") is True
        assert can_expression_run_with_no_input("empty") is True
        assert can_expression_run_with_no_input("range(10)") is True
        assert can_expression_run_with_no_input("range(1; 10)") is True

    def test_array_literals(self) -> None:
        """Test array literals without dots return True"""
        assert can_expression_run_with_no_input("[1, 2, 3]") is True
        assert can_expression_run_with_no_input('["a", "b", "c"]') is True
        assert can_expression_run_with_no_input("[true, false]") is True
        assert can_expression_run_with_no_input("[null, empty]") is True

    def test_object_literals(self) -> None:
        """Test object literals without dots return True"""
        assert can_expression_run_with_no_input('{"key": "value"}') is True
        assert can_expression_run_with_no_input('{"a": 1, "b": 2}') is True
        assert can_expression_run_with_no_input('{"flag": true}') is True

    def test_array_literals_with_dots(self) -> None:
        """Test array literals with dots return False"""
        assert can_expression_run_with_no_input("[.field, .other]") is False
        assert can_expression_run_with_no_input('["a", .field]') is False

    def test_object_literals_with_dots(self) -> None:
        """Test object literals with dots return False"""
        assert can_expression_run_with_no_input('{"key": .field}') is False
        assert can_expression_run_with_no_input('{"a": .field, "b": .other}') is False

    def test_string_operations(self) -> None:
        """Test string operations without dots return True"""
        assert can_expression_run_with_no_input('"hello" + "world"') is True
        assert can_expression_run_with_no_input('"a" + "b" + "c"') is True

    def test_number_operations(self) -> None:
        """Test number operations return True"""
        assert can_expression_run_with_no_input("1 + 2") is True
        assert can_expression_run_with_no_input("3 * 4") is True
        assert can_expression_run_with_no_input("10 / 2") is True
        assert can_expression_run_with_no_input("5 - 3") is True

    def test_decimal_number_operations(self) -> None:
        """Test decimal number operations return True (ensures decimal points in numbers don't require input)"""
        assert can_expression_run_with_no_input("3.14 + 2.5") is True
        assert can_expression_run_with_no_input("3.14 * 2.5") is True
        assert can_expression_run_with_no_input("10.5 / 2.5") is True
        assert can_expression_run_with_no_input("5.5 - 3.2") is True
        assert can_expression_run_with_no_input("3.14 + 2.5 * 1.5") is True
        assert can_expression_run_with_no_input("3.14") is True
        assert can_expression_run_with_no_input("-3.14") is True
        assert can_expression_run_with_no_input("+3.14") is True

    def test_mixed_operations(self) -> None:
        """Test mixed operations without dots return True"""
        assert can_expression_run_with_no_input('"hello" + 42') is True
        assert can_expression_run_with_no_input('42 + "world"') is True

    def test_operations_with_dots(self) -> None:
        """Test operations with dots return False"""
        assert can_expression_run_with_no_input(".field + .other") is False
        assert can_expression_run_with_no_input('"hello" + .field') is False
        assert can_expression_run_with_no_input('.field + "world"') is False

    def test_whitespace_handling(self) -> None:
        """Test whitespace handling"""
        assert can_expression_run_with_no_input("  null  ") is True
        assert can_expression_run_with_no_input("  true  ") is True
        assert can_expression_run_with_no_input("  false  ") is True
        assert can_expression_run_with_no_input("  42  ") is True
        assert can_expression_run_with_no_input('  "hello"  ') is True

    def test_complex_nullary_expressions(self) -> None:
        """Test complex nullary expressions"""
        assert can_expression_run_with_no_input("range(1; 10; 2)") is True
        assert can_expression_run_with_no_input("range(0; 100)") is True

    def test_edge_cases(self) -> None:
        """Test edge cases"""
        # Empty array
        assert can_expression_run_with_no_input("[]") is True
        # Empty object
        assert can_expression_run_with_no_input("{}") is True
        # Nested arrays
        assert can_expression_run_with_no_input("[[1, 2], [3, 4]]") is True
        # Nested objects
        assert can_expression_run_with_no_input('{"a": {"b": "c"}}') is True


class TestCanExpressionRunOnSingleItem:
    """Test the _can_expression_run_on_single_item function"""

    def test_empty_key(self) -> None:
        """Test empty key returns False"""
        assert _can_expression_run_on_single_item(".field", "") is False
        assert _can_expression_run_on_single_item("map(.field)", "") is False

    def test_key_at_start(self) -> None:
        """Test key at start of expression"""
        assert _can_expression_run_on_single_item(".item.field", "item") is True
        assert _can_expression_run_on_single_item(".item", "item") is True

    def test_key_in_middle(self) -> None:
        """Test key in middle of expression"""
        assert _can_expression_run_on_single_item(".data.item.field", "item") is False
        assert _can_expression_run_on_single_item(".body.item.yaeli", "item") is False

    def test_key_at_end(self) -> None:
        """Test key at end of expression"""
        assert _can_expression_run_on_single_item(".field.item", "item") is False

    def test_key_in_function(self) -> None:
        """Test key in function calls"""
        assert _can_expression_run_on_single_item("map(.item.field)", "item") is True
        assert (
            _can_expression_run_on_single_item("select(.item.status)", "item") is True
        )

    def test_key_in_pipe(self) -> None:
        """Test key in pipe operations"""
        assert _can_expression_run_on_single_item(".[] | .item.field", "item") is False
        assert (
            _can_expression_run_on_single_item(".data[] | .item.field", "item") is False
        )
        assert (
            _can_expression_run_on_single_item("[1,2,3,4] | .item.field", "item")
            is True
        )

    def test_key_in_array(self) -> None:
        """Test key in array literals"""
        assert (
            _can_expression_run_on_single_item("[.item.id, .item.name]", "item") is True
        )
        assert (
            _can_expression_run_on_single_item(
                "[.data.item.id, .body.item.name]", "item"
            )
            is False
        )

    def test_key_in_object(self) -> None:
        """Test key in object literals"""
        assert (
            _can_expression_run_on_single_item(
                "{id: .item.id, name: .item.name}", "item"
            )
            is True
        )
        assert (
            _can_expression_run_on_single_item(
                "{id: .data.item.id, name: .body.item.name}", "item"
            )
            is False
        )

    def test_key_in_conditional(self) -> None:
        """Test key in conditional expressions"""
        assert (
            _can_expression_run_on_single_item(
                "if .item.exists then .item.value else null end", "item"
            )
            is True
        )
        assert (
            _can_expression_run_on_single_item(
                "if .data.item.exists then .body.item.value else null end", "item"
            )
            is False
        )

    def test_key_in_string_ignored(self) -> None:
        """Test key in string literals is ignored"""
        assert (
            _can_expression_run_on_single_item('"this is .item in string"', "item")
            is False
        )
        assert (
            _can_expression_run_on_single_item(
                'select(.data.string == ".item")', "item"
            )
            is False
        )

    def test_key_with_word_boundaries(self) -> None:
        """Test key with proper word boundaries"""
        assert _can_expression_run_on_single_item(".item.field", "item") is True
        assert _can_expression_run_on_single_item(".item", "item") is True
        # Should not match if key is part of larger word
        assert _can_expression_run_on_single_item(".itemize.field", "item") is False
        assert _can_expression_run_on_single_item(".items.field", "item") is False
        assert _can_expression_run_on_single_item(".myitem.field", "item") is False

    def test_key_case_sensitive(self) -> None:
        """Test key matching is case sensitive"""
        assert _can_expression_run_on_single_item(".ITEM.field", "item") is False
        assert _can_expression_run_on_single_item(".Item.field", "item") is False
        assert _can_expression_run_on_single_item(".ITEM.field", "ITEM") is True

    def test_key_with_special_characters(self) -> None:
        """Test key with special characters"""
        assert _can_expression_run_on_single_item(".item[0].field", "item") is True
        assert _can_expression_run_on_single_item(".item.field[0]", "item") is True

    def test_key_not_present(self) -> None:
        """Test key not present in expression"""
        assert _can_expression_run_on_single_item(".field.other", "item") is False
        assert _can_expression_run_on_single_item(".data.field", "item") is False
        assert _can_expression_run_on_single_item("null", "item") is False
        assert _can_expression_run_on_single_item('"hello"', "item") is False

    def test_key_in_complex_expressions(self) -> None:
        """Test key in complex expressions"""
        assert (
            _can_expression_run_on_single_item(".data.items[] | .item.field", "item")
            is False
        )
        assert (
            _can_expression_run_on_single_item(
                "reduce .item.items[] as $item (0; . + $item.value)", "item"
            )
            is True
        )
        assert (
            _can_expression_run_on_single_item("group_by(.item.category)", "item")
            is True
        )
        assert (
            _can_expression_run_on_single_item("sort_by(.item.priority)", "item")
            is True
        )
        assert _can_expression_run_on_single_item("unique_by(.item.id)", "item") is True

    def test_key_with_escaped_strings(self) -> None:
        """Test key detection with escaped strings"""
        assert (
            _can_expression_run_on_single_item(
                '"hello \\"world\\"" + .item.field', "item"
            )
            is True
        )
        assert (
            _can_expression_run_on_single_item(
                '"this is .item in string" + .other.field', "item"
            )
            is False
        )


class TestClassifyInput:
    """Test the classify_input function"""

    def test_none_input(self) -> None:
        """Test expressions that require no input"""
        assert classify_input("null") == InputClassifyingResult.NONE
        assert classify_input("true") == InputClassifyingResult.NONE
        assert classify_input("false") == InputClassifyingResult.NONE
        assert classify_input("42") == InputClassifyingResult.NONE
        assert classify_input('"hello"') == InputClassifyingResult.NONE
        assert classify_input("[1, 2, 3]") == InputClassifyingResult.NONE
        assert classify_input('{"key": "value"}') == InputClassifyingResult.NONE
        assert classify_input("empty") == InputClassifyingResult.NONE
        assert classify_input("range(10)") == InputClassifyingResult.NONE
        assert classify_input('"hello" + "world"') == InputClassifyingResult.NONE
        assert classify_input("1 + 2") == InputClassifyingResult.NONE
        assert classify_input("") == InputClassifyingResult.NONE
        assert classify_input("   ") == InputClassifyingResult.NONE

    def test_single_input(self) -> None:
        """Test expressions that can run on single item"""
        assert classify_input(".item.field", "item") == InputClassifyingResult.SINGLE
        assert classify_input(".item", "item") == InputClassifyingResult.SINGLE
        assert (
            classify_input("map(.item.field)", "item") == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("select(.item.status)", "item")
            == InputClassifyingResult.SINGLE
        )
        assert classify_input(".[] | .item.field", "item") == InputClassifyingResult.ALL
        assert (
            classify_input("[.item.id, .item.name]", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("{id: .item.id, name: .item.name}", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("if .item.exists then .item.value else null end", "item")
            == InputClassifyingResult.SINGLE
        )

    def test_all_input(self) -> None:
        """Test expressions that require all input"""
        assert classify_input(".field") == InputClassifyingResult.ALL
        assert classify_input(".data.field") == InputClassifyingResult.ALL
        assert classify_input("map(.field)") == InputClassifyingResult.ALL
        assert classify_input("select(.field)") == InputClassifyingResult.ALL
        assert classify_input(".[] | .field") == InputClassifyingResult.ALL
        assert classify_input("[.field, .other]") == InputClassifyingResult.ALL
        assert (
            classify_input("{id: .field, name: .other}") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("if .field.exists then .other.value else null end")
            == InputClassifyingResult.ALL
        )

    def test_single_input_without_key(self) -> None:
        """Test single input expressions without key parameter"""
        assert classify_input(".item.field") == InputClassifyingResult.ALL
        assert classify_input("map(.item.field)") == InputClassifyingResult.ALL
        assert classify_input("select(.item.status)") == InputClassifyingResult.ALL

    def test_single_input_with_different_key(self) -> None:
        """Test single input expressions with different key"""
        assert classify_input(".item.field", "other") == InputClassifyingResult.ALL
        assert classify_input(".data.item.field", "other") == InputClassifyingResult.ALL
        assert classify_input("map(.item.field)", "other") == InputClassifyingResult.ALL

    def test_edge_cases(self) -> None:
        """Test edge cases"""
        # Empty key
        assert classify_input(".item.field", "") == InputClassifyingResult.ALL
        # None key
        assert classify_input(".item.field", None) == InputClassifyingResult.ALL
        # Key in string (should not match)
        assert (
            classify_input('"this is .item in string"', "item")
            == InputClassifyingResult.NONE
        )
        # Key with word boundaries
        assert classify_input(".itemize.field", "item") == InputClassifyingResult.ALL
        assert classify_input(".items.field", "item") == InputClassifyingResult.ALL
        assert classify_input(".myitem.field", "item") == InputClassifyingResult.ALL

    def test_complex_expressions(self) -> None:
        """Test complex expressions"""
        # Complex single input expressions
        assert (
            classify_input(".data.items[] | .item.field", "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input("reduce .item.items[] as $item (0; . + $item.value)", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("group_by(.item.category)", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("sort_by(.item.priority)", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("unique_by(.item.id)", "item")
            == InputClassifyingResult.SINGLE
        )

        # Complex all input expressions
        assert (
            classify_input(".data.items[] | .field.item", "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input("reduce .data.items[] as $item (0; . + $item.value)", "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input("group_by(.data.category)", "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input("sort_by(.data.priority)", "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input("unique_by(.data.id)", "item") == InputClassifyingResult.ALL
        )

    def test_input_dependent_functions(self) -> None:
        """Test input-dependent functions"""
        # These should all require ALL input regardless of key
        assert classify_input("map(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("select(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("length(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("keys(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("values(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("has(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("in(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("index(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("indices(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("contains(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("paths(.field)", "item") == InputClassifyingResult.ALL
        assert (
            classify_input("leaf_paths(.field)", "item") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("to_entries(.field)", "item") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("from_entries(.field)", "item") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("with_entries(.field)", "item") == InputClassifyingResult.ALL
        )
        assert classify_input("del(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("delpaths(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("walk(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("reduce(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("foreach(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("input(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("inputs(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("limit(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("first(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("last(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("nth(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("while(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("until(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("recurse(.field)", "item") == InputClassifyingResult.ALL
        assert (
            classify_input("recurse_down(.field)", "item") == InputClassifyingResult.ALL
        )
        assert classify_input("bsearch(.field)", "item") == InputClassifyingResult.ALL
        assert (
            classify_input("combinations(.field)", "item") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("permutations(.field)", "item") == InputClassifyingResult.ALL
        )

    def test_whitespace_handling(self) -> None:
        """Test whitespace handling"""
        assert classify_input("  null  ") == InputClassifyingResult.NONE
        assert classify_input("  true  ") == InputClassifyingResult.NONE
        assert classify_input("  false  ") == InputClassifyingResult.NONE
        assert classify_input("  42  ") == InputClassifyingResult.NONE
        assert classify_input('  "hello"  ') == InputClassifyingResult.NONE
        assert (
            classify_input("  .item.field  ", "item") == InputClassifyingResult.SINGLE
        )
        assert classify_input("  .field  ") == InputClassifyingResult.ALL

    def test_string_operations(self) -> None:
        """Test string operations"""
        assert classify_input('"hello" + "world"') == InputClassifyingResult.NONE
        assert classify_input('"hello" + .field') == InputClassifyingResult.ALL
        assert classify_input('.field + "world"') == InputClassifyingResult.ALL
        assert (
            classify_input('.item.field + "world"', "item")
            == InputClassifyingResult.SINGLE
        )

    def test_number_operations(self) -> None:
        """Test number operations"""
        assert classify_input("1 + 2") == InputClassifyingResult.NONE
        assert classify_input("3 * 4") == InputClassifyingResult.NONE
        assert classify_input("10 / 2") == InputClassifyingResult.NONE
        assert classify_input("5 - 3") == InputClassifyingResult.NONE
        assert classify_input(".field + 2") == InputClassifyingResult.ALL
        assert (
            classify_input(".item.field + 2", "item") == InputClassifyingResult.SINGLE
        )

    def test_array_operations(self) -> None:
        """Test array operations"""
        assert classify_input("[1, 2, 3]") == InputClassifyingResult.NONE
        assert classify_input("[.field, .other]") == InputClassifyingResult.ALL
        assert (
            classify_input("[.item.field, .item.other]", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("[.data.item.field, .body.item.other]", "item")
            == InputClassifyingResult.ALL
        )

    def test_object_operations(self) -> None:
        """Test object operations"""
        assert classify_input('{"key": "value"}') == InputClassifyingResult.NONE
        assert classify_input('{"key": .field}') == InputClassifyingResult.ALL
        assert (
            classify_input('{"key": .item.field}', "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('{"key": .data.item.field}', "item")
            == InputClassifyingResult.ALL
        )

    def test_conditional_operations(self) -> None:
        """Test conditional operations"""
        assert (
            classify_input("if true then 1 else 0 end") == InputClassifyingResult.NONE
        )
        assert (
            classify_input("if .field then 1 else 0 end") == InputClassifyingResult.ALL
        )
        assert (
            classify_input("if .item.field then 1 else 0 end", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("if .data.item.field then 1 else 0 end", "item")
            == InputClassifyingResult.ALL
        )

    def test_range_operations(self) -> None:
        """Test range operations"""
        assert classify_input("range(10)") == InputClassifyingResult.NONE
        assert classify_input("range(1; 10)") == InputClassifyingResult.NONE
        assert classify_input("range(1; 10; 2)") == InputClassifyingResult.NONE
        assert classify_input("range(.field)") == InputClassifyingResult.ALL
        assert (
            classify_input("range(.item.field)", "item")
            == InputClassifyingResult.SINGLE
        )

    def test_complex_mixed_expressions(self) -> None:
        """Test complex mixed expressions"""
        # Mixed nullary expressions
        assert classify_input('"hello" + 42') == InputClassifyingResult.NONE
        assert classify_input('42 + "world"') == InputClassifyingResult.NONE
        assert classify_input('[1, "hello", true]') == InputClassifyingResult.NONE

        # Mixed single input expressions
        assert (
            classify_input('"hello" + .item.field', "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('.item.field + "world"', "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('[.item.id, "hello", .item.name]', "item")
            == InputClassifyingResult.SINGLE
        )

        # Mixed all input expressions
        assert classify_input('"hello" + .field') == InputClassifyingResult.ALL
        assert classify_input('.field + "world"') == InputClassifyingResult.ALL
        assert classify_input('[.field, "hello", .other]') == InputClassifyingResult.ALL


class TestInputClassifyingResult:
    """Test the InputClassifyingResult enum"""

    def test_enum_values(self) -> None:
        """Test enum values"""
        assert InputClassifyingResult.NONE.value == 1
        assert InputClassifyingResult.SINGLE.value == 2
        assert InputClassifyingResult.ALL.value == 3

    def test_enum_names(self) -> None:
        """Test enum names"""
        assert InputClassifyingResult.NONE.name == "NONE"
        assert InputClassifyingResult.SINGLE.name == "SINGLE"
        assert InputClassifyingResult.ALL.name == "ALL"

    def test_enum_comparison(self) -> None:
        """Test enum comparison"""
        assert InputClassifyingResult.NONE != InputClassifyingResult.SINGLE
        assert InputClassifyingResult.SINGLE != InputClassifyingResult.ALL
        assert InputClassifyingResult.NONE != InputClassifyingResult.ALL
        assert InputClassifyingResult.NONE == InputClassifyingResult.NONE
        assert InputClassifyingResult.SINGLE == InputClassifyingResult.SINGLE
        assert InputClassifyingResult.ALL == InputClassifyingResult.ALL

    def test_enum_string_representation(self) -> None:
        """Test enum string representation"""
        assert str(InputClassifyingResult.NONE) == "InputClassifyingResult.NONE"
        assert str(InputClassifyingResult.SINGLE) == "InputClassifyingResult.SINGLE"
        assert str(InputClassifyingResult.ALL) == "InputClassifyingResult.ALL"

    def test_enum_repr(self) -> None:
        """Test enum repr"""
        assert repr(InputClassifyingResult.NONE) == "<InputClassifyingResult.NONE: 1>"
        assert (
            repr(InputClassifyingResult.SINGLE) == "<InputClassifyingResult.SINGLE: 2>"
        )
        assert repr(InputClassifyingResult.ALL) == "<InputClassifyingResult.ALL: 3>"


class TestIntegration:
    """Integration tests for the jq_input_evaluator module"""

    def test_real_world_scenarios(self) -> None:
        """Test real-world scenarios"""
        # Blueprint mapping scenarios
        assert (
            classify_input('"newRelicService"', "item") == InputClassifyingResult.NONE
        )
        assert (
            classify_input('"newRelicService" in mapping', "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input('.item.blueprint == "newRelicService"', "item")
            == InputClassifyingResult.SINGLE
        )

        # Entity property scenarios
        assert classify_input(".item.name", "item") == InputClassifyingResult.SINGLE
        assert (
            classify_input(".item.description", "item") == InputClassifyingResult.SINGLE
        )
        assert classify_input(".item.status", "item") == InputClassifyingResult.SINGLE
        assert classify_input(".data.name", "item") == InputClassifyingResult.ALL
        assert classify_input(".data.description", "item") == InputClassifyingResult.ALL

        # Selector scenarios
        assert (
            classify_input('.item.status == "active"', "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('.item.type == "service"', "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('.data.status == "active"', "item")
            == InputClassifyingResult.ALL
        )
        assert (
            classify_input('.data.type == "service"', "item")
            == InputClassifyingResult.ALL
        )

        # Complex mapping scenarios
        assert (
            classify_input("map(.item.field)", "item") == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input('select(.item.status == "active")', "item")
            == InputClassifyingResult.SINGLE
        )
        assert classify_input(".[] | .item.field", "item") == InputClassifyingResult.ALL
        assert (
            classify_input("[.item.id, .item.name]", "item")
            == InputClassifyingResult.SINGLE
        )
        assert (
            classify_input("{id: .item.id, name: .item.name}", "item")
            == InputClassifyingResult.SINGLE
        )

        # Static value scenarios
        assert classify_input('"static_value"', "item") == InputClassifyingResult.NONE
        assert classify_input("null", "item") == InputClassifyingResult.NONE
        assert classify_input("true", "item") == InputClassifyingResult.NONE
        assert classify_input("false", "item") == InputClassifyingResult.NONE
        assert classify_input("42", "item") == InputClassifyingResult.NONE

    def test_performance_scenarios(self) -> None:
        """Test performance-related scenarios"""
        # Large expressions
        large_expr = " + ".join([f'"{i}"' for i in range(100)])
        assert classify_input(large_expr, "item") == InputClassifyingResult.NONE

        # Complex nested expressions
        complex_expr = "if .item.exists then .item.value else .item.default end"
        assert classify_input(complex_expr, "item") == InputClassifyingResult.SINGLE

        # Multiple function calls
        multi_func_expr = "map(.item.field) | select(.item.status) | .item.value"
        assert classify_input(multi_func_expr, "item") == InputClassifyingResult.SINGLE

    def test_edge_case_scenarios(self) -> None:
        """Test edge case scenarios"""
        # Empty expressions
        assert classify_input("", "item") == InputClassifyingResult.NONE
        assert classify_input("   ", "item") == InputClassifyingResult.NONE

        # Single character expressions
        assert classify_input(".", "item") == InputClassifyingResult.ALL
        assert classify_input("a", "item") == InputClassifyingResult.NONE

        # Very long expressions
        long_expr = " + ".join([f'"{i}"' for i in range(1000)])
        assert classify_input(long_expr, "item") == InputClassifyingResult.NONE

        # Expressions with special characters
        assert classify_input('.item["field"]', "item") == InputClassifyingResult.SINGLE
        assert (
            classify_input('.item["field"]["subfield"]', "item")
            == InputClassifyingResult.SINGLE
        )
        assert classify_input(".item.field[0]", "item") == InputClassifyingResult.SINGLE
        assert (
            classify_input(".item.field[0].subfield", "item")
            == InputClassifyingResult.SINGLE
        )

    def test_consistency_scenarios(self) -> None:
        """Test consistency scenarios"""
        # Same expression with different keys should be consistent
        expr = ".field.other"
        assert classify_input(expr, "item") == InputClassifyingResult.ALL
        assert classify_input(expr, "field") == InputClassifyingResult.SINGLE
        assert classify_input(expr, "other") == InputClassifyingResult.ALL

        # Same expression with different keys should be consistent
        expr = ".data.item.field"
        assert classify_input(expr, "item") == InputClassifyingResult.ALL
        assert classify_input(expr, "data") == InputClassifyingResult.SINGLE
        assert classify_input(expr, "field") == InputClassifyingResult.ALL

        # Same expression with different keys should be consistent
        expr = "map(.item.field)"
        assert classify_input(expr, "item") == InputClassifyingResult.SINGLE
        assert classify_input(expr, "field") == InputClassifyingResult.ALL
        assert classify_input(expr, "other") == InputClassifyingResult.ALL

    def test_error_handling_scenarios(self) -> None:
        """Test error handling scenarios"""
        # Invalid expressions should still be classified
        assert classify_input(".invalid.field", "item") == InputClassifyingResult.ALL
        assert classify_input("invalid(.field)", "item") == InputClassifyingResult.ALL
        assert classify_input("invalid", "item") == InputClassifyingResult.NONE

        # Malformed expressions should still be classified
        assert classify_input("..field", "item") == InputClassifyingResult.ALL
        assert classify_input(".field.", "item") == InputClassifyingResult.ALL
        assert classify_input("field.", "item") == InputClassifyingResult.ALL

        # Expressions with syntax errors should still be classified
        assert classify_input(".field +", "item") == InputClassifyingResult.ALL
        assert classify_input("+ .field", "item") == InputClassifyingResult.ALL
        assert classify_input(".field + + .other", "item") == InputClassifyingResult.ALL
