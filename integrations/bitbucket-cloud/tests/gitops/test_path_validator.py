import pytest
from bitbucket_cloud.gitops.path_validator import (
    match_spec_paths,
    match_path_pattern,
)


def test_match_spec_paths_with_list() -> None:
    """Test matching spec paths with a list of patterns."""
    file_path = "specs/port.yml"
    target_path = "specs/port.yaml"
    spec_paths = ["specs/*.yml", "specs/*.yaml"]

    result = match_spec_paths(file_path, target_path, spec_paths)
    assert file_path in result
    assert target_path in result


def test_match_spec_paths_with_string() -> None:
    """Test matching spec paths with a single string pattern."""
    file_path = "specs/port.yml"
    target_path = "specs/other.yml"  # Not a port config file
    spec_path = "specs/*.yml"

    result = match_spec_paths(file_path, target_path, spec_path)
    assert file_path in result
    assert target_path not in result


def test_match_spec_paths_no_match() -> None:
    """Test when no paths match the patterns."""
    file_path = "src/port.yml"
    target_path = "src/port.yaml"
    spec_paths = ["specs/*.yml"]

    result = match_spec_paths(file_path, target_path, spec_paths)
    assert not result


def test_match_path_pattern() -> None:
    """Test matching individual path patterns."""
    # Test valid port config files
    assert match_path_pattern("specs/port.yml", "specs/*.yml")
    assert match_path_pattern("specs/port.yaml", "specs/*.yaml")
    assert match_path_pattern("specs/nested/port.yml", "specs/**/*.yml")

    # Test non-port config files
    assert not match_path_pattern("specs/service.yml", "specs/*.yml")
    assert not match_path_pattern("specs/config.yaml", "specs/*.yaml")

    # Test different paths
    assert not match_path_pattern("other/port.yml", "specs/*.yml")


@pytest.mark.parametrize(
    "file_path,spec_path,expected",
    [
        ("specs/port.yml", "specs/*.yml", True),
        ("specs/port.yaml", "specs/*.yaml", True),
        ("specs/nested/port.yml", "specs/**/*.yml", True),
        ("specs/nested/port.yaml", "**/port.yaml", True),
        ("port.yaml", "**/port.yaml", True),
        ("other/port.yml", "specs/*.yml", False),
        ("specs/service.yml", "specs/*.yml", False),
        ("specs/config.yaml", "specs/*.yaml", False),
        ("", "specs/*.yml", False),
    ],
)
def test_match_path_pattern_parametrized(
    file_path: str, spec_path: str, expected: bool
) -> None:
    """Test path pattern matching with various combinations."""
    assert match_path_pattern(file_path, spec_path) == expected
