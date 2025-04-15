import pytest
from unittest.mock import patch
from azure_devops.client.file_processing import (
    match_pattern,
    expand_patterns,
    get_base_paths,
    generate_file_object_from_repository_file,
    parse_file_content,
)


class TestPatternMatching:
    def test_match_pattern_with_string(self) -> None:
        """Test the match_pattern function with string patterns."""
        # Basic pattern matching
        assert match_pattern("*.json", "file.json") is True
        assert match_pattern("*.json", "file.yaml") is False

        # Directory pattern matching
        assert match_pattern("dir/*.json", "dir/file.json") is True
        assert match_pattern("dir/*.json", "other/file.json") is False

        # Double-star pattern matching
        assert match_pattern("**/file.json", "dir/file.json") is True
        assert match_pattern("**/file.json", "dir/subdir/file.json") is True

    def test_match_pattern_with_list(self) -> None:
        """Test the match_pattern function with lists of patterns."""
        # Test with a list of patterns
        patterns = ["*.json", "*.yaml", "*.yml"]
        assert match_pattern(patterns, "file.json") is True
        assert match_pattern(patterns, "file.yaml") is True
        assert match_pattern(patterns, "file.yml") is True
        assert match_pattern(patterns, "file.txt") is False

        # Test with a more complex list
        patterns = ["src/**/*.js", "tests/**/*.js", "*.json"]
        assert match_pattern(patterns, "src/components/Button.js") is True
        assert match_pattern(patterns, "tests/unit/button.test.js") is True
        assert match_pattern(patterns, "package.json") is True
        assert match_pattern(patterns, "styles/main.css") is False

    def test_match_pattern_with_leading_slash(self) -> None:
        """Test that leading slashes are handled correctly."""
        assert match_pattern("dir/file.json", "/dir/file.json") is True
        assert match_pattern("**/file.json", "/path/to/file.json") is True

    def test_match_pattern_error_handling(self) -> None:
        """Test error handling in match_pattern."""
        # Test with a non-string input that would cause an error
        with patch("azure_devops.client.file_processing.logger") as mock_logger:
            # Using None as the string will cause an error in the function
            result = match_pattern("*.json", None)  # type: ignore
            assert result is False
            mock_logger.error.assert_called_once()


class TestPatternExpansion:
    def test_expand_patterns_with_string(self) -> None:
        """Test the expand_patterns function with string input."""
        # Test with no braces
        patterns = expand_patterns("src/**/*.js")
        assert patterns == ["src/**/*.js"]

        # Test with simple brace expansion
        patterns = expand_patterns("src/**/*.{js,ts}")
        assert len(patterns) == 2
        assert "src/**/*.js" in patterns
        assert "src/**/*.ts" in patterns

    def test_expand_patterns_with_list(self) -> None:
        """Test the expand_patterns function with list input."""
        # Test with a list of patterns
        patterns = expand_patterns(["src/**/*.js", "tests/**/*.js"])
        assert len(patterns) == 2
        assert "src/**/*.js" in patterns
        assert "tests/**/*.js" in patterns

        # Test with brace expansion in the list
        patterns = expand_patterns(["src/**/*.{js,ts}", "tests/**/*.js"])
        assert len(patterns) == 3
        assert "src/**/*.js" in patterns
        assert "src/**/*.ts" in patterns
        assert "tests/**/*.js" in patterns


class TestBasePaths:
    def test_get_base_paths(self) -> None:
        """Test the get_base_paths function."""
        # Test with simple patterns
        base_paths = get_base_paths(["src/components/*.js", "src/utils/*.js"])
        assert len(base_paths) == 2
        assert "src/components" in base_paths
        assert "src/utils" in base_paths

        # Test with wildcard in directory
        base_paths = get_base_paths(["src/*/components/*.js"])
        assert len(base_paths) == 1
        assert "/" in base_paths

        # Test with double-star pattern
        base_paths = get_base_paths(["**/components/*.js"])
        assert len(base_paths) == 1
        assert "**" in base_paths

        # Test with mixed patterns
        base_paths = get_base_paths(["src/components/*.js", "**/utils/*.js"])
        assert len(base_paths) == 2
        assert "src/components" in base_paths
        assert "**" in base_paths


class TestContentParsing:
    @pytest.mark.asyncio
    async def test_parse_json_content(self) -> None:
        """Test parsing JSON content."""
        # Test with valid JSON
        json_content = b'{"name": "test", "value": 123}'
        result = await parse_file_content(json_content)
        assert result == {"name": "test", "value": 123}

        # Test with more complex JSON
        complex_json = (
            b'{"name": "test", "values": [1, 2, 3], "nested": {"key": "value"}}'
        )
        result = await parse_file_content(complex_json)
        assert isinstance(result, dict)
        assert result.get("name") == "test"
        assert result.get("values") == [1, 2, 3]
        assert isinstance(result.get("nested"), dict)
        assert result.get("nested", {}).get("key") == "value"

    @pytest.mark.asyncio
    async def test_parse_yaml_content(self) -> None:
        """Test parsing YAML content."""
        # Test with simple YAML
        yaml_content = b"name: test\nvalue: 123"
        result = await parse_file_content(yaml_content)
        assert result == {"name": "test", "value": 123}

        # Test with more complex YAML
        complex_yaml = b"""
        name: test
        values:
          - 1
          - 2
          - 3
        nested:
          key: value
        """
        result = await parse_file_content(complex_yaml)
        assert isinstance(result, dict)
        assert result.get("name") == "test"
        assert result.get("values") == [1, 2, 3]
        assert isinstance(result.get("nested"), dict)
        assert result.get("nested", {}).get("key") == "value"

        # Test with multi-document YAML
        multi_yaml = b"---\nname: doc1\n---\nname: doc2"
        result = await parse_file_content(multi_yaml)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].get("name") == "doc1"
        assert result[1].get("name") == "doc2"


class TestFileProcessing:
    @pytest.mark.asyncio
    async def test_generate_file_object_from_repository_file_json(self) -> None:
        """Test processing JSON file content."""
        # Test with JSON file
        file_metadata = {"path": "test.json", "size": 30}
        file_content = b'{"name": "test", "value": 123}'
        repo_metadata = {"id": "repo1", "name": "Test Repo"}

        result = await generate_file_object_from_repository_file(
            file_metadata, file_content, repo_metadata
        )

        assert result is not None
        assert result["file"]["path"] == "test.json"
        assert result["file"]["size"] == 30
        assert result["file"]["content"]["raw"] == '{"name": "test", "value": 123}'
        assert result["file"]["content"]["parsed"] == {"name": "test", "value": 123}
        assert result["repo"] == repo_metadata

    @pytest.mark.asyncio
    async def test_generate_file_object_from_repository_file_yaml(self) -> None:
        """Test processing YAML file content."""
        # Test with YAML file
        file_metadata = {"path": "test.yaml", "size": 21}
        file_content = b"name: test\nvalue: 123"
        repo_metadata = {"id": "repo1", "name": "Test Repo"}

        result = await generate_file_object_from_repository_file(
            file_metadata, file_content, repo_metadata
        )

        assert result is not None
        assert result["file"]["path"] == "test.yaml"
        assert result["file"]["size"] == 21
        assert result["file"]["content"]["raw"] == "name: test\nvalue: 123"
        assert result["file"]["content"]["parsed"] == {"name": "test", "value": 123}
        assert result["repo"] == repo_metadata

    @pytest.mark.asyncio
    async def test_generate_file_object_from_repository_file_size_fallback(
        self,
    ) -> None:
        """Test that size falls back to content length."""
        # Test with size in metadata
        file_metadata = {"path": "test.json", "size": 100}
        file_content = b'{"name": "test"}'
        repo_metadata = {"id": "repo1", "name": "Test Repo"}

        result = await generate_file_object_from_repository_file(
            file_metadata, file_content, repo_metadata
        )

        assert result is not None
        assert result["file"]["size"] == 16
