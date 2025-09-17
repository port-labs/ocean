import pytest
from typing import Any, Dict

from github.helpers.utils import (
    create_search_params,
    enrich_with_repository,
    extract_repo_params,
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
    """Tests for extract_repo_params function."""

    def test_extract_basic_params(self) -> None:
        """Test extracting repo name from basic params."""
        params = {"repo_name": "test-repo", "other_param": "value"}

        repo_name, remaining_params = extract_repo_params(params)

        assert repo_name == "test-repo"
        assert remaining_params == {"other_param": "value"}
        assert "repo_name" not in remaining_params

    def test_extract_modifies_original_dict(self) -> None:
        """Test that extraction modifies the original dict."""
        params = {"repo_name": "test-repo", "other_param": "value"}
        original_params = params.copy()
        original_id = id(params)

        repo_name, remaining_params = extract_repo_params(params)

        assert repo_name == original_params["repo_name"]
        assert id(remaining_params) == original_id  # Same dict object
        assert "repo_name" not in params  # Original dict modified
        assert params == {"other_param": "value"}

    def test_extract_only_repo_name(self) -> None:
        """Test extracting when only repo_name is present."""
        params = {"repo_name": "test-repo"}

        repo_name, remaining_params = extract_repo_params(params)

        assert repo_name == "test-repo"
        assert remaining_params == {}

    def test_extract_with_multiple_params(self) -> None:
        """Test extracting with multiple other parameters."""
        params = {
            "repo_name": "test-repo",
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

        repo_name, remaining_params = extract_repo_params(params)

        assert repo_name == "test-repo"
        assert remaining_params == {
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

    def test_extract_missing_repo_name(self) -> None:
        """Test that missing repo_name raises KeyError."""
        params = {"other_param": "value"}

        with pytest.raises(KeyError, match="repo_name"):
            extract_repo_params(params)

    def test_extract_empty_dict(self) -> None:
        """Test that empty dict raises KeyError."""
        params: Dict[str, Any] = {}

        with pytest.raises(KeyError, match="repo_name"):
            extract_repo_params(params)

    def test_extract_with_none_repo_name(self) -> None:
        """Test extracting with None repo name."""
        params = {"repo_name": None, "other_param": "value"}

        repo_name, remaining_params = extract_repo_params(params)

        assert repo_name is None
        assert remaining_params == {"other_param": "value"}


class TestCreateSearchParams:
    def test_create_search_params(self) -> None:
        # Test case 1: Empty list of repos
        assert list(create_search_params([])) == []

        # Test case 2: List with less than max_operators repos
        repos = ["repo1", "repo2", "repo3"]
        expected = ["repo1 in:name OR repo2 in:name OR repo3 in:name"]
        assert list(create_search_params(repos)) == expected

        # Test case 3: List with exactly max_operators + 1 repos (default is 5+1=6).
        # All repo names are short, so they should fit in one query.
        repos = ["r1", "r2", "r3", "r4", "r5", "r6"]
        expected = [
            "r1 in:name OR r2 in:name OR r3 in:name OR r4 in:name OR r5 in:name OR r6 in:name"
        ]
        assert list(create_search_params(repos)) == expected

        # Test case 4: List with more than max_operators + 1 repos.
        repos = ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]
        expected = [
            "r1 in:name OR r2 in:name OR r3 in:name OR r4 in:name OR r5 in:name OR r6 in:name",
            "r7 in:name",
        ]
        assert list(create_search_params(repos)) == expected

        # Test case 5: List of repos where the total length exceeds the character limit.
        # A repo name of length 42, becomes 50 characters with "+in+name".
        # 5 such repos with 4 "OR"s is 5 * 50 + 4 * 2 = 258 characters, which is > 256.
        # So the query should be split into a chunk of 4 and a chunk of 3.
        repo_base = "a" * 40
        repos = [f"{repo_base}-{i}" for i in range(7)]
        expected = [
            " OR ".join([f"{r} in:name" for r in repos[:4]]),
            " OR ".join([f"{r} in:name" for r in repos[4:]]),
        ]
        assert list(create_search_params(repos)) == expected

        # Test case 6: A single repo name that is too long to fit in a query.
        long_repo_name = "a" * 250
        repos = [long_repo_name]
        # The function logs a warning and does not add long repo to search string
        assert list(create_search_params(repos)) == []
