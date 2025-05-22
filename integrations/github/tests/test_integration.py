# tests/test_github_client.py
"""
Focused tests for the GitHub integration's main functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import base64
from github.clients.github_client import GitHubClient
from github.clients.rest_client import RestClient
from github.clients.auth_client import AuthClient


class TestGitHubClient:
    """Test the main GitHub client functionality."""

    @pytest.fixture
    def github_client(self):
        """Create a GitHubClient instance for testing."""
        return GitHubClient("https://api.github.com", "fake-token")

    @pytest.mark.asyncio
    async def test_get_repository(self, github_client):
        """Test getting a single repository."""
        expected_repo = {
            "id": 123,
            "full_name": "owner/repo",
            "name": "repo",
            "html_url": "https://github.com/owner/repo"
        }

        with patch.object(github_client.rest, 'send_api_request') as mock_request:
            mock_request.return_value = expected_repo

            result = await github_client.get_repository("owner/repo")

            assert result == expected_repo
            mock_request.assert_called_once_with("GET", "repos/owner%2Frepo")

    @pytest.mark.asyncio
    async def test_get_repositories_with_languages(self, github_client):
        """Test getting repositories with language enrichment."""
        mock_repos = [{"full_name": "owner/repo1", "id": 1}]
        mock_languages = {"Python": 1000, "JavaScript": 500}

        with patch.object(github_client.rest, 'get_paginated_resource') as mock_paginated, \
             patch.object(github_client.rest, 'get_repo_languages') as mock_get_languages:

            async def mock_async_gen():
                yield mock_repos

            mock_paginated.return_value = mock_async_gen()
            mock_get_languages.return_value = mock_languages

            repos_list = []
            async for repos_batch in github_client.get_repositories(include_languages=True):
                repos_list.extend(repos_batch)

            assert len(repos_list) == 1
            assert "__languages" in repos_list[0]
            assert repos_list[0]["__languages"] == mock_languages

    @pytest.mark.asyncio
    async def test_get_file_content(self, github_client):
        """Test getting file content from a repository."""
        expected_content = "# This is a README"

        with patch.object(github_client.rest, 'get_file_content') as mock_file_content:
            mock_file_content.return_value = expected_content

            result = await github_client.get_file_content("owner/repo", "README.md")

            assert result == expected_content
            mock_file_content.assert_called_once_with("owner/repo", "README.md", "main")


class TestRestClient:
    """Test the REST client functionality."""

    @pytest.fixture
    def rest_client(self):
        """Create a RestClient instance for testing."""
        return RestClient("https://api.github.com", "fake-token")

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, rest_client):
        """Test successfully getting file content."""
        content = "Hello, World!"
        encoded_content = base64.b64encode(content.encode()).decode()

        mock_response = {
            "content": encoded_content,
            "encoding": "base64"
        }

        with patch.object(rest_client, 'send_api_request') as mock_request:
            mock_request.return_value = mock_response

            result = await rest_client.get_file_content("owner/repo", "hello.txt")

            assert result == content

    @pytest.mark.asyncio
    async def test_get_repo_languages(self, rest_client):
        """Test getting repository languages."""
        expected_languages = {"Python": 5000, "JavaScript": 2000}

        with patch.object(rest_client, 'send_api_request') as mock_request:
            mock_request.return_value = expected_languages

            result = await rest_client.get_repo_languages("owner/repo")

            assert result == expected_languages
            mock_request.assert_called_once_with("GET", "repos/owner%2Frepo/languages", params={})


class TestAuthClient:
    """Test the authentication client."""

    def test_get_headers(self):
        """Test getting authentication headers."""
        auth_client = AuthClient("test-token")
        headers = auth_client.get_headers()

        expected_headers = {
            "Authorization": "token test-token",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

        assert headers == expected_headers


class TestEntityProcessors:
    """Test entity processors without PortOcean context."""

    @pytest.mark.asyncio
    async def test_file_entity_processor(self):
        """Test FileEntityProcessor functionality."""
        from github.entity_processors.entity_processor import FileEntityProcessor

        # Mock the client creation to avoid PortOcean context
        with patch('github.entity_processors.entity_processor.create_github_client') as mock_create:
            mock_client = AsyncMock()
            mock_client.get_file_content.return_value = "File content"
            mock_create.return_value = mock_client

            processor = FileEntityProcessor(context=MagicMock())

            data = {
                "full_name": "owner/repo",
                "default_branch": "main"
            }

            result = await processor._search(data, "file://README.md")

            assert result == "File content"
            mock_client.get_file_content.assert_called_once_with("owner/repo", "README.md", "main")

    @pytest.mark.asyncio
    async def test_search_entity_processor(self):
        """Test SearchEntityProcessor functionality."""
        from github.entity_processors.entity_processor import SearchEntityProcessor

        with patch('github.entity_processors.entity_processor.create_github_client') as mock_create:
            mock_client = AsyncMock()
            mock_client.file_exists.return_value = True
            mock_create.return_value = mock_client

            processor = SearchEntityProcessor(context=MagicMock())

            data = {"full_name": "owner/repo"}

            result = await processor._search(data, "search://path=Dockerfile")

            assert result is True
            mock_client.file_exists.assert_called_once_with("owner/repo", "Dockerfile")


class TestUtils:
    """Test utility functions."""

    def test_parse_json_content(self):
        """Test parsing JSON file content."""
        from github.helpers.utils import parse_file_content

        json_content = '{"key": "value", "number": 42}'
        result = parse_file_content(json_content, "test.json", "test-context")

        assert result == {"key": "value", "number": 42}

    def test_parse_yaml_content(self):
        """Test parsing YAML file content."""
        from github.helpers.utils import parse_file_content

        yaml_content = """
        key: value
        number: 42
        """
        result = parse_file_content(yaml_content, "test.yaml", "test-context")

        assert result["key"] == "value"
        assert result["number"] == 42


# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def sample_repository():
    """Sample repository data for testing."""
    return {
        "id": 123456789,
        "full_name": "octocat/Hello-World",
        "name": "Hello-World",
        "owner": {
            "login": "octocat",
            "id": 1
        },
        "html_url": "https://github.com/octocat/Hello-World",
        "description": "This your first repo!",
        "private": False,
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 80,
        "created_at": "2011-01-26T19:01:12Z",
        "updated_at": "2011-01-26T19:14:43Z"
    }


@pytest.fixture
def sample_pull_request():
    """Sample pull request data for testing."""
    return {
        "id": 1,
        "number": 1347,
        "state": "open",
        "title": "Amazing new feature",
        "user": {
            "login": "octocat",
            "id": 1
        },
        "body": "Please pull these awesome changes in!",
        "created_at": "2011-01-26T19:01:12Z",
        "updated_at": "2011-01-26T19:14:43Z",
        "html_url": "https://github.com/octocat/Hello-World/pull/1347"
    }
