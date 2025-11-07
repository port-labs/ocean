import pytest
from typing import Any, Dict

from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
)


class TestEnrichWithRepository:
    """Tests for enrich_with_repository function."""

    def test_enrich_with_default_key(self) -> None:
        """Test enriching response with default key."""
        response = {"data": "test"}
        repo_name = "test-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert result["data"] == "test"
        assert result is response  # Should modify original dict

    def test_enrich_with_custom_key(self) -> None:
        """Test enriching response with custom key."""
        response = {"data": "test"}
        repo_name = "test-repo"
        custom_key = "repository_info"

        result = enrich_with_repository(response, repo_name, custom_key)

        assert result[custom_key] == repo_name
        assert result["data"] == "test"
        assert "__repository" not in result

    def test_enrich_empty_response(self) -> None:
        """Test enriching empty response."""
        response: Dict[str, Any] = {}
        repo_name = "test-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert len(result) == 1

    def test_enrich_overwrites_existing_key(self) -> None:
        """Test that enriching overwrites existing key."""
        response = {"__repository": "old-repo", "data": "test"}
        repo_name = "new-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert result["data"] == "test"

    def test_enrich_with_empty_string_repo_name(self) -> None:
        """Test enriching with empty string repo name."""
        response = {"data": "test"}
        repo_name = ""

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == ""
        assert result["data"] == "test"


class TestExtractRepoParams:
    """Tests for parse_github_options function."""

    def test_extract_basic_params(self) -> None:
        """Test extracting repo name from basic params."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "other_param": "value",
        }

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}
        assert "repo_name" not in remaining_params
        assert "organization" not in remaining_params

    def test_extract_modifies_original_dict(self) -> None:
        """Test that extraction modifies the original dict."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "other_param": "value",
        }
        original_params = params.copy()
        original_id = id(params)

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == original_params["repo_name"]
        assert organization == original_params["organization"]
        assert id(remaining_params) == original_id  # Same dict object
        assert "repo_name" not in params  # Original dict modified
        assert "organization" not in params  # Original dict modified
        assert params == {"other_param": "value"}

    def test_extract_only_repo_name(self) -> None:
        """Test extracting when only repo_name is present."""
        params = {"organization": "test-org", "repo_name": "test-repo"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {}

    def test_extract_with_multiple_params(self) -> None:
        """Test extracting with multiple other parameters."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

    def test_extract_missing_repo_name(self) -> None:
        """Test that missing repo_name raises KeyError."""
        params = {"organization": "test-org", "other_param": "value"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name is None
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}

    def test_extract_empty_dict(self) -> None:
        """Test that empty dict raises KeyError."""
        params: Dict[str, Any] = {}

        with pytest.raises(KeyError, match="organization"):
            parse_github_options(params)

    def test_extract_with_none_repo_name(self) -> None:
        """Test extracting with None repo name."""
        params = {"organization": "test-org", "repo_name": None, "other_param": "value"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name is None
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}
