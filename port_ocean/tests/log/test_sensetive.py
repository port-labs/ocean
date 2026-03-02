"""Tests for the SensitiveLogFilter class."""

from typing import Any, Generator

import pytest

from port_ocean.log.sensetive import SensitiveLogFilter


@pytest.fixture(autouse=True)
def reset_compiled_patterns() -> Generator[None, None, None]:
    """Reset compiled_patterns to default state before each test.

    SensitiveLogFilter.compiled_patterns is a class-level list that persists
    across instances. This fixture ensures test isolation by saving and
    restoring the original patterns.
    """
    original_patterns = SensitiveLogFilter.compiled_patterns.copy()
    yield
    SensitiveLogFilter.compiled_patterns = original_patterns


class TestMaskObject:
    """Tests for the mask_object method."""

    def test_mask_object_does_not_mutate_original_dict(self) -> None:
        """Test that mask_object returns a new dict and leaves original unchanged."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("secret-token")

        original = {"url": "https://secret-token.example.com/api"}
        original_copy = {"url": "https://secret-token.example.com/api"}

        result = log_filter.mask_object(original, full_hide=True)

        assert original == original_copy  # Original unchanged
        assert "[REDACTED]" in result["url"]  # Result is masked
        assert result is not original  # Different object

    def test_mask_object_does_not_mutate_nested_dicts(self) -> None:
        """Test that nested dicts are also not mutated."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("secret-org")

        original: dict[str, Any] = {
            "id": "123",
            "__project": {"url": "https://secret-org.example.com/project"},
        }
        nested_url_before = original["__project"]["url"]

        result: dict[str, Any] = log_filter.mask_object(original, full_hide=True)

        assert original["__project"]["url"] == nested_url_before  # Nested unchanged
        assert "[REDACTED]" in result["__project"]["url"]  # Result nested is masked

    def test_mask_object_does_not_mutate_lists(self) -> None:
        """Test that lists containing dicts are not mutated."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("secret")

        original = [{"key": "secret-value"}, {"key": "other"}]

        result: list[dict[str, Any]] = log_filter.mask_object(original, full_hide=True)

        assert original[0]["key"] == "secret-value"  # Original unchanged
        assert "[REDACTED]" in result[0]["key"]  # Result is masked

    def test_mask_object_deeply_nested_structure(self) -> None:
        """Test that deeply nested structures are not mutated."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("https://dev.azure.com/myorg")

        original: dict[str, Any] = {
            "id": "board-123",
            "name": "Sprint Board",
            "url": "https://dev.azure.com/myorg/project/_apis/work/boards/123",
            "__project": {
                "id": "project-456",
                "name": "My Project",
                "url": "https://dev.azure.com/myorg/_apis/projects/456",
            },
            "_links": {
                "self": {
                    "href": "https://dev.azure.com/myorg/project/_apis/work/boards/123"
                },
                "project": {"href": "https://dev.azure.com/myorg/_apis/projects/456"},
            },
        }

        # Store original values
        original_url = original["url"]
        original_project_url = original["__project"]["url"]
        original_self_href = original["_links"]["self"]["href"]

        result: dict[str, Any] = log_filter.mask_object(original, full_hide=True)

        # Verify original is unchanged
        assert original["url"] == original_url
        assert original["__project"]["url"] == original_project_url
        assert original["_links"]["self"]["href"] == original_self_href

        # Verify result is masked
        assert "[REDACTED]" in result["url"]
        assert "[REDACTED]" in result["__project"]["url"]
        assert "[REDACTED]" in result["_links"]["self"]["href"]


class TestMaskString:
    """Tests for the mask_string method."""

    def test_mask_string_with_sensitive_pattern(self) -> None:
        """Test that strings containing sensitive patterns are masked."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("my-secret")

        result = log_filter.mask_string(
            "url: https://my-secret.example.com", full_hide=True
        )

        assert "[REDACTED]" in result
        assert "my-secret" not in result

    def test_mask_string_partial_hide(self) -> None:
        """Test that partial hide keeps first 6 characters."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("secrettoken123")

        result = log_filter.mask_string("token is secrettoken123", full_hide=False)

        assert "secret[REDACTED]" in result

    def test_mask_string_no_match(self) -> None:
        """Test that strings without sensitive patterns are unchanged."""
        log_filter = SensitiveLogFilter()
        log_filter.hide_sensitive_strings("secret")

        original = "this string has no sensitive data"
        result = log_filter.mask_string(original, full_hide=True)

        assert result == original


class TestHideSensitiveStrings:
    """Tests for the hide_sensitive_strings method."""

    def test_hide_sensitive_strings_adds_patterns(self) -> None:
        """Test that hide_sensitive_strings adds patterns to the filter."""
        log_filter = SensitiveLogFilter()
        initial_count = len(log_filter.compiled_patterns)

        log_filter.hide_sensitive_strings("pattern1", "pattern2")

        assert len(log_filter.compiled_patterns) == initial_count + 2

    def test_hide_sensitive_strings_ignores_empty(self) -> None:
        """Test that empty strings are ignored."""
        log_filter = SensitiveLogFilter()
        initial_count = len(log_filter.compiled_patterns)

        log_filter.hide_sensitive_strings("", "  ", "valid")

        assert len(log_filter.compiled_patterns) == initial_count + 1
