import pytest

from port_ocean.core.integrations.mixins.utils import (
    extract_jq_deletion_path_revised,
)

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
