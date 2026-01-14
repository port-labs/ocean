"""Unit tests for Harbor utility functions."""

import pytest

from harbor.utils import parse_resource_url, split_repository_name


class TestParseResourceUrl:
    """Tests for parse_resource_url function."""

    def test_parse_resource_url_with_tag(self) -> None:
        """Test parsing resource URL with tag reference."""
        resource_url = "harbor.example.com:8081/library/nginx:latest"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "library"
        assert repo == "nginx"
        assert ref == "latest"

    def test_parse_resource_url_with_digest(self) -> None:
        """Test parsing resource URL with digest reference."""
        resource_url = "harbor.example.com:8081/library/nginx@sha256:abc123def456"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "library"
        assert repo == "nginx"
        assert ref == "sha256:abc123def456"

    def test_parse_resource_url_with_version_tag(self) -> None:
        """Test parsing resource URL with version tag."""
        resource_url = "harbor.example.com/myproject/myapp:v1.2.3"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "myproject"
        assert repo == "myapp"
        assert ref == "v1.2.3"

    def test_parse_resource_url_with_nested_repository(self) -> None:
        """Test parsing resource URL with nested repository path."""
        resource_url = "harbor.example.com/project/sub/repo:tag"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "project"
        assert repo == "sub/repo"
        assert ref == "tag"

    def test_parse_resource_url_localhost(self) -> None:
        """Test parsing resource URL with localhost."""
        resource_url = "localhost:8080/opensource/nginx:latest"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "opensource"
        assert repo == "nginx"
        assert ref == "latest"

    def test_parse_resource_url_invalid_format_no_separator(self) -> None:
        """Test parsing resource URL with invalid format (no tag/digest separator)."""
        resource_url = "harbor.example.com/library/nginx"
        with pytest.raises(ValueError, match="No tag or digest separator found"):
            parse_resource_url(resource_url)

    def test_parse_resource_url_invalid_format_no_slash(self) -> None:
        """Test parsing resource URL with invalid format (no slash)."""
        resource_url = "harbor.example.com:8081"
        with pytest.raises(ValueError, match="Invalid resource_url format"):
            parse_resource_url(resource_url)

    def test_parse_resource_url_invalid_format_no_project(self) -> None:
        """Test parsing resource URL with invalid format (no project)."""
        resource_url = "harbor.example.com/nginx:latest"
        with pytest.raises(ValueError, match="Invalid repository path format"):
            parse_resource_url(resource_url)

    def test_parse_resource_url_with_port_and_digest(self) -> None:
        """Test parsing resource URL with port and digest."""
        resource_url = "registry.harbor.io:443/prod/app@sha256:1234567890abcdef"
        project, repo, ref = parse_resource_url(resource_url)

        assert project == "prod"
        assert repo == "app"
        assert ref == "sha256:1234567890abcdef"


class TestSplitRepositoryName:
    """Tests for split_repository_name function."""

    def test_split_repository_name_valid(self) -> None:
        """Test splitting a valid repository name."""
        repo_name = "library/nginx"
        project, repo = split_repository_name(repo_name)

        assert project == "library"
        assert repo == "nginx"

    def test_split_repository_name_with_nested_path(self) -> None:
        """Test splitting repository name with nested path."""
        repo_name = "project/sub/path/repo"
        project, repo = split_repository_name(repo_name)

        assert project == "project"
        assert repo == "sub/path/repo"

    def test_split_repository_name_invalid_no_slash(self) -> None:
        """Test splitting repository name without slash."""
        repo_name = "nginx"
        with pytest.raises(ValueError, match="Invalid repository name format"):
            split_repository_name(repo_name)

    def test_split_repository_name_invalid_empty(self) -> None:
        """Test splitting empty repository name."""
        repo_name = ""
        with pytest.raises(ValueError, match="Invalid repository name format"):
            split_repository_name(repo_name)

    def test_split_repository_name_with_multiple_projects(self) -> None:
        """Test splitting repository name that looks like multiple projects."""
        repo_name = "org/team/project/app"
        project, repo = split_repository_name(repo_name)

        # Should only split on first slash
        assert project == "org"
        assert repo == "team/project/app"

