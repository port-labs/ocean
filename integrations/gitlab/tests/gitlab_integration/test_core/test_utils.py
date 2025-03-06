import pytest

from gitlab_integration.core.utils import (
    convert_glob_to_gitlab_patterns,
    does_pattern_apply,
    generate_ref,
)


@pytest.mark.parametrize(
    "pattern,string,expected",
    [
        # Single string pattern that should match
        ("foo*", "foobar", True),
        # Single string pattern that should not match
        ("bar", "foo", False),
        # List of patterns, one should match
        (["foo*", "bar*"], "barbaz", True),
        # List of patterns, none should match
        (["foo*", "bar*"], "baz", False),
        # Exact match
        ("hello", "hello", True),
        # Another wildcard test
        ("hello*", "hello123", True),
        # Another wildcard not matching
        ("world*", "hello", False),
        # Empty pattern should not match anything
        ("", "anything", False),
        # List of patterns including an empty pattern
        (["", "foo*"], "food", True),
        (["**/port.yml", "**/port.yaml"], "port.yml", True),
        ("**/port.yml", "port.yml", True),
        ("**port.yaml", "port.yaml", True),
    ],
)
def test_does_pattern_apply(
    pattern: str | list[str], string: str, expected: bool
) -> None:
    assert does_pattern_apply(pattern, string) == expected


@pytest.mark.parametrize(
    "pattern,expected",
    [
        # Single pattern with brace expansion
        ("foo/{bar,baz}", ["foo/bar", "foo/baz"]),
        # Multiple braces
        ("a{b,c}d{e,f}", ["abde", "abdf", "acde", "acdf"]),
        # No braces - should be returned as is
        ("foo", ["foo"]),
        # List of patterns, some with braces
        (["foo/{bar,baz}", "spam/eggs"], ["foo/bar", "foo/baz", "spam/eggs"]),
        # Empty string in a list
        (["", "abc"], ["", "abc"]),
    ],
)
def test_convert_glob_to_gitlab_patterns(
    pattern: str | list[str], expected: list[str]
) -> None:
    assert convert_glob_to_gitlab_patterns(pattern) == expected


@pytest.mark.parametrize(
    "branch_name,expected",
    [
        ("main", "refs/heads/main"),
        ("feature/test", "refs/heads/feature/test"),
        ("", "refs/heads/"),
        ("some-branch-name", "refs/heads/some-branch-name"),
    ],
)
def test_generate_ref(branch_name: str, expected: str) -> None:
    assert generate_ref(branch_name) == expected
