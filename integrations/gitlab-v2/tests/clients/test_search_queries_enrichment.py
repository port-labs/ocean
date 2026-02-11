"""Tests for the search queries enrichment feature in GitLabClient."""

from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


async def async_mock_generator(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


@pytest.mark.asyncio
class TestSearchQueriesEnrichment:
    """Tests for _enrich_project_with_search_queries method."""

    @pytest.fixture
    def client(self) -> GitLabClient:
        return GitLabClient("https://gitlab.example.com", "test-token")

    @pytest.fixture
    def sample_project(self) -> dict[str, Any]:
        return {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "group/test-project",
            "default_branch": "main",
        }

    async def test_enrich_with_single_search_query_found(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment with a single search query that finds results."""
        search_queries = [
            {"name": "hasPortYml", "scope": "blobs", "query": "filename:port.yml"}
        ]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=True)
        ) as mock_file_exists:
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert "__searchQueries" in result
            assert result["__searchQueries"]["hasPortYml"] is True
            mock_file_exists.assert_called_once_with(
                "group/test-project", "blobs", "filename:port.yml"
            )

    async def test_enrich_with_single_search_query_not_found(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment with a single search query that finds no results."""
        search_queries = [
            {"name": "hasDockerfile", "scope": "blobs", "query": "filename:Dockerfile"}
        ]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=False)
        ) as mock_file_exists:
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert "__searchQueries" in result
            assert result["__searchQueries"]["hasDockerfile"] is False
            mock_file_exists.assert_called_once_with(
                "group/test-project", "blobs", "filename:Dockerfile"
            )

    async def test_enrich_with_multiple_search_queries(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment with multiple search queries returning mixed results."""
        search_queries = [
            {"name": "hasPortYml", "scope": "blobs", "query": "filename:port.yml"},
            {"name": "hasDockerfile", "scope": "blobs", "query": "filename:Dockerfile"},
            {
                "name": "hasMakefile",
                "scope": "blobs",
                "query": "filename:Makefile",
            },
        ]

        with patch.object(
            client,
            "file_exists",
            AsyncMock(side_effect=[True, False, True]),
        ):
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert result["__searchQueries"]["hasPortYml"] is True
            assert result["__searchQueries"]["hasDockerfile"] is False
            assert result["__searchQueries"]["hasMakefile"] is True

    async def test_enrich_with_empty_search_queries(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment with an empty search queries list."""
        result = await client._enrich_project_with_search_queries(sample_project, [])

        assert "__searchQueries" in result
        assert result["__searchQueries"] == {}

    async def test_enrich_with_search_query_error(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment when a search query raises an exception."""
        search_queries = [
            {"name": "failQuery", "scope": "blobs", "query": "filename:fail.txt"},
            {"name": "successQuery", "scope": "blobs", "query": "filename:ok.txt"},
        ]

        with patch.object(
            client,
            "file_exists",
            AsyncMock(side_effect=[Exception("API error"), True]),
        ):
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert result["__searchQueries"]["failQuery"] is None
            assert result["__searchQueries"]["successQuery"] is True

    async def test_enrich_with_default_scope(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment uses 'blobs' as default scope when scope is omitted."""
        search_queries = [
            {"name": "hasReadme", "query": "filename:README.md"},
        ]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=True)
        ) as mock_file_exists:
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert result["__searchQueries"]["hasReadme"] is True
            mock_file_exists.assert_called_once_with(
                "group/test-project", "blobs", "filename:README.md"
            )

    async def test_enrich_with_non_blobs_scope(
        self, client: GitLabClient, sample_project: dict[str, Any]
    ) -> None:
        """Test enrichment with a non-default scope (e.g., commits)."""
        search_queries = [
            {"name": "hasFixCommit", "scope": "commits", "query": "fix"},
        ]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=True)
        ) as mock_file_exists:
            result = await client._enrich_project_with_search_queries(
                sample_project, search_queries
            )

            assert result["__searchQueries"]["hasFixCommit"] is True
            mock_file_exists.assert_called_once_with(
                "group/test-project", "commits", "fix"
            )

    async def test_enrich_preserves_existing_project_data(
        self, client: GitLabClient
    ) -> None:
        """Test that enrichment preserves existing project data fields."""
        project = {
            "id": 456,
            "name": "Another Project",
            "path_with_namespace": "org/another-project",
            "default_branch": "develop",
            "description": "Test description",
            "__languages": {"Python": 80.0},
        }
        search_queries = [
            {"name": "hasCI", "scope": "blobs", "query": "filename:.gitlab-ci.yml"}
        ]

        with patch.object(client, "file_exists", AsyncMock(return_value=True)):
            result = await client._enrich_project_with_search_queries(
                project, search_queries
            )

            # All original fields should be preserved
            assert result["id"] == 456
            assert result["name"] == "Another Project"
            assert result["description"] == "Test description"
            assert result["__languages"] == {"Python": 80.0}
            # And search results should be added
            assert result["__searchQueries"]["hasCI"] is True

    async def test_enrich_uses_path_with_namespace_for_project_id(
        self, client: GitLabClient
    ) -> None:
        """Test that enrichment uses path_with_namespace as the project identifier."""
        project = {
            "id": 789,
            "path_with_namespace": "my-org/my-project",
        }
        search_queries = [{"name": "test", "scope": "blobs", "query": "test"}]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=True)
        ) as mock_file_exists:
            await client._enrich_project_with_search_queries(project, search_queries)

            mock_file_exists.assert_called_once_with(
                "my-org/my-project", "blobs", "test"
            )

    async def test_enrich_falls_back_to_id_when_no_path(
        self, client: GitLabClient
    ) -> None:
        """Test that enrichment falls back to string ID when path_with_namespace is missing."""
        project = {
            "id": 789,
        }
        search_queries = [{"name": "test", "scope": "blobs", "query": "test"}]

        with patch.object(
            client, "file_exists", AsyncMock(return_value=True)
        ) as mock_file_exists:
            await client._enrich_project_with_search_queries(project, search_queries)

            mock_file_exists.assert_called_once_with("789", "blobs", "test")


@pytest.mark.asyncio
class TestGetProjectsWithSearchQueries:
    """Tests for get_projects with search_queries parameter."""

    @pytest.fixture
    def client(self) -> GitLabClient:
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_get_projects_with_search_queries(self, client: GitLabClient) -> None:
        """Test that get_projects passes search_queries to enrichment."""
        mock_projects = [
            {
                "id": 1,
                "name": "Test Project",
                "path_with_namespace": "test/project",
            }
        ]
        search_queries = [
            {"name": "hasPortYml", "scope": "blobs", "query": "filename:port.yml"}
        ]

        with (
            patch.object(
                client.rest,
                "get_paginated_resource",
                return_value=async_mock_generator([mock_projects]),
            ),
            patch.object(
                client,
                "file_exists",
                AsyncMock(return_value=True),
            ),
        ):
            results = []
            async for batch in client.get_projects(
                search_queries=search_queries,
            ):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["__searchQueries"]["hasPortYml"] is True

    async def test_get_projects_without_search_queries(
        self, client: GitLabClient
    ) -> None:
        """Test that get_projects works without search_queries."""
        mock_projects = [
            {
                "id": 1,
                "name": "Test Project",
                "path_with_namespace": "test/project",
            }
        ]

        with patch.object(
            client.rest,
            "get_paginated_resource",
            return_value=async_mock_generator([mock_projects]),
        ):
            results = []
            async for batch in client.get_projects():
                results.extend(batch)

            assert len(results) == 1
            assert "__searchQueries" not in results[0]

    async def test_get_projects_with_languages_and_search_queries(
        self, client: GitLabClient
    ) -> None:
        """Test that get_projects can combine language enrichment and search queries."""
        mock_projects = [
            {
                "id": 1,
                "name": "Test Project",
                "path_with_namespace": "test/project",
            }
        ]
        mock_languages = {"Python": 80.0, "Shell": 20.0}
        search_queries = [
            {"name": "hasCI", "scope": "blobs", "query": "filename:.gitlab-ci.yml"}
        ]

        with (
            patch.object(
                client.rest,
                "get_paginated_resource",
                return_value=async_mock_generator([mock_projects]),
            ),
            patch.object(
                client.rest,
                "get_project_languages",
                AsyncMock(return_value=mock_languages),
            ),
            patch.object(
                client,
                "file_exists",
                AsyncMock(return_value=True),
            ),
        ):
            results = []
            async for batch in client.get_projects(
                include_languages=True,
                search_queries=search_queries,
            ):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["__languages"] == mock_languages
            assert results[0]["__searchQueries"]["hasCI"] is True


@pytest.mark.asyncio
class TestGetProjectWithSearchQueries:
    """Tests for get_project (single) with search_queries parameter."""

    @pytest.fixture
    def client(self) -> GitLabClient:
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_get_project_with_search_queries(self, client: GitLabClient) -> None:
        """Test that get_project applies search queries enrichment."""
        mock_project = {
            "id": 123,
            "path_with_namespace": "group/project",
            "default_branch": "main",
        }
        search_queries = [
            {"name": "hasPortYml", "scope": "blobs", "query": "filename:port.yml"}
        ]

        with (
            patch.object(
                client.rest,
                "send_api_request",
                AsyncMock(return_value=mock_project),
            ),
            patch.object(
                client,
                "file_exists",
                AsyncMock(return_value=True),
            ),
        ):
            result = await client.get_project(
                "group/project", search_queries=search_queries
            )

            assert result["__searchQueries"]["hasPortYml"] is True

    async def test_get_project_without_search_queries(
        self, client: GitLabClient
    ) -> None:
        """Test that get_project works without search_queries."""
        mock_project = {
            "id": 123,
            "path_with_namespace": "group/project",
        }

        with patch.object(
            client.rest,
            "send_api_request",
            AsyncMock(return_value=mock_project),
        ):
            result = await client.get_project("group/project")

            assert "__searchQueries" not in result
