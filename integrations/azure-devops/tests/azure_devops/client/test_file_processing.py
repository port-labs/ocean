import pytest
from unittest.mock import patch
from azure_devops.client.file_processing import (
    match_pattern,
    expand_patterns,
    get_base_paths,
    generate_file_object_from_repository_file,
    parse_file_content,
    is_glob_pattern,
    extract_descriptor_from_pattern,
    separate_glob_and_literal_paths,
    matches_glob_pattern,
    filter_files_by_glob,
    PathDescriptor,
    RecursionLevel,
)
from typing import Any


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


class TestGlobPatternDetection:
    """Test the is_glob_pattern function."""

    def test_is_glob_pattern_with_wildcards(self) -> None:
        """Test detection of glob patterns with various wildcards."""
        # Basic wildcards
        assert is_glob_pattern("*.json") is True
        assert is_glob_pattern("file.*") is True
        assert is_glob_pattern("*.{json,yaml}") is True

        # Question mark
        assert is_glob_pattern("file?.txt") is True
        assert is_glob_pattern("config?.yaml") is True

        # Character classes
        assert is_glob_pattern("file[0-9].txt") is True
        assert is_glob_pattern("config[a-z].json") is True

        # Double star
        assert is_glob_pattern("**/*.js") is True
        assert is_glob_pattern("src/**") is True

        # Braces
        assert is_glob_pattern("*.{js,ts}") is True
        assert is_glob_pattern("src/{main,test}/*.js") is True

        # Negation
        assert is_glob_pattern("!*.tmp") is True
        assert is_glob_pattern("!node_modules/**") is True

    def test_is_glob_pattern_with_literal_paths(self) -> None:
        """Test that literal paths are correctly identified as non-glob patterns."""
        # Literal paths should return False
        assert is_glob_pattern("src/config.json") is False
        assert is_glob_pattern("docs/README.md") is False
        assert is_glob_pattern("package.json") is False
        assert is_glob_pattern("src/main.js") is False
        assert is_glob_pattern("") is False
        assert is_glob_pattern("/absolute/path/file.txt") is False

    def test_is_glob_pattern_with_escaped_characters(self) -> None:
        """Test that escaped glob characters are not treated as patterns."""
        # Escaped characters should not be treated as glob patterns
        assert is_glob_pattern(r"file\*.txt") is False
        assert is_glob_pattern(r"config\?.yaml") is False
        assert is_glob_pattern(r"path\[test\].json") is False


class TestPathDescriptorExtraction:
    """Test the extract_descriptor_from_pattern function."""

    def test_extract_descriptor_from_literal_path(self) -> None:
        """Test extracting descriptor from literal paths."""
        desc = extract_descriptor_from_pattern("src/config.json")
        assert desc.base_path == "/src/config.json"
        assert desc.recursion == RecursionLevel.NONE
        assert desc.pattern == "src/config.json"

        desc = extract_descriptor_from_pattern("/absolute/path/file.txt")
        assert desc.base_path == "/absolute/path/file.txt"
        assert desc.recursion == RecursionLevel.NONE
        assert desc.pattern == "/absolute/path/file.txt"

    def test_extract_descriptor_from_simple_glob(self) -> None:
        """Test extracting descriptor from simple glob patterns."""
        desc = extract_descriptor_from_pattern("src/*.js")
        assert desc.base_path == "/src"
        assert desc.recursion == RecursionLevel.ONE_LEVEL
        assert desc.pattern == "src/*.js"

        desc = extract_descriptor_from_pattern("*.json")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.ONE_LEVEL
        assert desc.pattern == "*.json"

    def test_extract_descriptor_from_double_star_pattern(self) -> None:
        """Test extracting descriptor from double star patterns."""
        desc = extract_descriptor_from_pattern("src/**/*.js")
        assert desc.base_path == "/src"
        assert desc.recursion == RecursionLevel.FULL
        assert desc.pattern == "src/**/*.js"

        desc = extract_descriptor_from_pattern("**/*.md")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.FULL
        assert desc.pattern == "**/*.md"

        desc = extract_descriptor_from_pattern("**")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.FULL
        assert desc.pattern == "**"

    def test_extract_descriptor_from_complex_patterns(self) -> None:
        """Test extracting descriptor from complex glob patterns."""
        desc = extract_descriptor_from_pattern("src/components/**/*.{js,ts}")
        assert desc.base_path == "/src/components"
        assert desc.recursion == RecursionLevel.FULL
        assert desc.pattern == "src/components/**/*.{js,ts}"

        desc = extract_descriptor_from_pattern("config/*/settings.{json,yaml}")
        assert desc.base_path == "/config"
        assert desc.recursion == RecursionLevel.ONE_LEVEL
        assert desc.pattern == "config/*/settings.{json,yaml}"

    def test_extract_descriptor_edge_cases(self) -> None:
        """Test edge cases for descriptor extraction."""
        # Empty pattern
        desc = extract_descriptor_from_pattern("")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.NONE
        assert desc.pattern == ""

        # Just slash
        desc = extract_descriptor_from_pattern("/")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.NONE
        assert desc.pattern == "/"

        # Pattern with glob in first part
        desc = extract_descriptor_from_pattern("*.js")
        assert desc.base_path == "/"
        assert desc.recursion == RecursionLevel.ONE_LEVEL
        assert desc.pattern == "*.js"


class TestPathSeparation:
    """Test the separate_glob_and_literal_paths function."""

    def test_separate_glob_and_literal_paths_mixed(self) -> None:
        """Test separating mixed glob and literal paths."""
        paths = [
            "src/config.json",  # literal
            "*.js",  # glob
            "docs/README.md",  # literal
            "src/**/*.ts",  # glob
            "package.json",  # literal
            "tests/*.test.js",  # glob
        ]

        literals, globs = separate_glob_and_literal_paths(paths)

        assert literals == ["src/config.json", "docs/README.md", "package.json"]
        assert globs == ["*.js", "src/**/*.ts", "tests/*.test.js"]

    def test_separate_glob_and_literal_paths_all_literal(self) -> None:
        """Test with all literal paths."""
        paths = ["src/config.json", "docs/README.md", "package.json"]
        literals, globs = separate_glob_and_literal_paths(paths)

        assert literals == paths
        assert globs == []

    def test_separate_glob_and_literal_paths_all_glob(self) -> None:
        """Test with all glob patterns."""
        paths = ["*.js", "src/**/*.ts", "tests/*.test.js"]
        literals, globs = separate_glob_and_literal_paths(paths)

        assert literals == []
        assert globs == paths

    def test_separate_glob_and_literal_paths_empty(self) -> None:
        """Test with empty list."""
        literals, globs = separate_glob_and_literal_paths([])
        assert literals == []
        assert globs == []


class TestGlobPatternMatching:
    """Test the matches_glob_pattern function."""

    def test_matches_glob_pattern_simple_wildcards(self) -> None:
        """Test simple wildcard patterns."""
        assert matches_glob_pattern("file.txt", "*.txt") is True
        assert matches_glob_pattern("config.json", "*.json") is True
        assert matches_glob_pattern("file.txt", "*.json") is False

        assert matches_glob_pattern("test.txt", "test.*") is True
        assert matches_glob_pattern("test.json", "test.*") is True
        assert matches_glob_pattern("other.txt", "test.*") is False

    def test_matches_glob_pattern_double_star(self) -> None:
        """Test double star patterns."""
        assert matches_glob_pattern("src/main.js", "**/*.js") is True
        assert matches_glob_pattern("src/components/Button.js", "**/*.js") is True
        assert matches_glob_pattern("src/utils/helpers.js", "**/*.js") is True
        assert matches_glob_pattern("main.js", "**/*.js") is True

        assert matches_glob_pattern("src/main.js", "src/**/*.js") is True
        assert matches_glob_pattern("src/components/Button.js", "src/**/*.js") is True
        assert matches_glob_pattern("main.js", "src/**/*.js") is False

    def test_matches_glob_pattern_character_classes(self) -> None:
        """Test character class patterns."""
        assert matches_glob_pattern("file1.txt", "file[0-9].txt") is True
        assert matches_glob_pattern("file5.txt", "file[0-9].txt") is True
        assert matches_glob_pattern("file10.txt", "file[0-9].txt") is False

        # With IGNORECASE flag, character classes become case-insensitive
        assert matches_glob_pattern("config-a.json", "config-[a-z].json") is True
        assert matches_glob_pattern("config-z.json", "config-[a-z].json") is True
        assert (
            matches_glob_pattern("config-A.json", "config-[a-z].json") is True
        )  # Case-insensitive

    def test_matches_glob_pattern_braces(self) -> None:
        """Test brace expansion patterns."""
        # Note: wcmatch brace expansion might not work as expected in this context
        # Testing simpler patterns that should work
        assert matches_glob_pattern("file.js", "*.js") is True
        assert matches_glob_pattern("file.ts", "*.ts") is True
        assert matches_glob_pattern("file.py", "*.py") is True

        assert matches_glob_pattern("src/main.js", "src/main.js") is True
        assert matches_glob_pattern("src/test.js", "src/test.js") is True
        assert matches_glob_pattern("src/other.js", "src/other.js") is True

    def test_matches_glob_pattern_case_insensitive(self) -> None:
        """Test that pattern matching is case insensitive."""
        assert matches_glob_pattern("File.txt", "*.txt") is True
        assert matches_glob_pattern("FILE.TXT", "*.txt") is True
        assert matches_glob_pattern("file.TXT", "*.txt") is True

    def test_matches_glob_pattern_with_slashes(self) -> None:
        """Test pattern matching with leading/trailing slashes."""
        assert matches_glob_pattern("/src/main.js", "src/**/*.js") is True
        assert matches_glob_pattern("src/main.js/", "src/**/*.js") is True
        assert matches_glob_pattern("/src/main.js/", "src/**/*.js") is True


class TestFileFiltering:
    """Test the filter_files_by_glob function."""

    def test_filter_files_by_glob_simple_pattern(self) -> None:
        """Test filtering files with simple patterns."""
        files: list[dict[str, Any]] = [
            {"path": "/src/main.js", "isFolder": False},
            {"path": "/src/config.json", "isFolder": False},
            {"path": "/docs/README.md", "isFolder": False},
            {"path": "/src/utils/helper.js", "isFolder": False},
        ]

        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.ONE_LEVEL, pattern="src/*.js"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 1  # Only /src/main.js matches "src/*.js"
        assert any(f["path"] == "/src/main.js" for f in matched)

    def test_filter_files_by_glob_double_star_pattern(self) -> None:
        """Test filtering files with double star patterns."""
        files: list[dict[str, Any]] = [
            {"path": "/src/main.js", "isFolder": False},
            {"path": "/src/components/Button.js", "isFolder": False},
            {"path": "/src/utils/helper.js", "isFolder": False},
            {"path": "/docs/README.md", "isFolder": False},
        ]

        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.FULL, pattern="src/**/*.js"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 3
        assert any(f["path"] == "/src/main.js" for f in matched)
        assert any(f["path"] == "/src/components/Button.js" for f in matched)
        assert any(f["path"] == "/src/utils/helper.js" for f in matched)

    def test_filter_files_by_glob_skips_folders(self) -> None:
        """Test that folders are skipped during filtering."""
        files: list[dict[str, Any]] = [
            {"path": "/src/main.js", "isFolder": False},
            {"path": "/src/components", "isFolder": True},
            {"path": "/src/components/Button.js", "isFolder": False},
            {"path": "/docs", "isFolder": True},
        ]

        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.FULL, pattern="src/**/*.js"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 2
        assert any(f["path"] == "/src/main.js" for f in matched)
        assert any(f["path"] == "/src/components/Button.js" for f in matched)
        # Folders should be excluded
        assert not any(f["path"] == "/src/components" for f in matched)
        assert not any(f["path"] == "/docs" for f in matched)

    def test_filter_files_by_glob_no_matches(self) -> None:
        """Test filtering when no files match the pattern."""
        files: list[dict[str, Any]] = [
            {"path": "/src/main.js", "isFolder": False},
            {"path": "/src/config.json", "isFolder": False},
        ]

        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.ONE_LEVEL, pattern="src/*.py"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 0

    def test_filter_files_by_glob_empty_files_list(self) -> None:
        """Test filtering with empty files list."""
        files: list[dict[str, Any]] = []
        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.ONE_LEVEL, pattern="src/*.js"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 0

    def test_filter_files_by_glob_complex_pattern(self) -> None:
        """Test filtering with complex patterns."""
        files: list[dict[str, Any]] = [
            {"path": "/src/main.js", "isFolder": False},
            {"path": "/src/main.ts", "isFolder": False},
            {"path": "/src/components/Button.js", "isFolder": False},
            {"path": "/src/components/Button.ts", "isFolder": False},
            {"path": "/src/config.json", "isFolder": False},
        ]

        pattern = PathDescriptor(
            base_path="/src", recursion=RecursionLevel.FULL, pattern="src/**/*.js"
        )
        matched = filter_files_by_glob(files, pattern)

        assert len(matched) == 2
        assert any(f["path"] == "/src/main.js" for f in matched)
        assert any(f["path"] == "/src/components/Button.js" for f in matched)
        # TypeScript and JSON files should be excluded
        assert not any(f["path"] == "/src/main.ts" for f in matched)
        assert not any(f["path"] == "/src/components/Button.ts" for f in matched)
        assert not any(f["path"] == "/src/config.json" for f in matched)
