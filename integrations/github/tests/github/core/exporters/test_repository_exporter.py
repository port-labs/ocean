from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
    GraphQLRepositoryExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import (
    SingleRepositoryOptions,
    ListRepositoryOptions,
    SingleGraphQLRepositoryOptions,
    ListGraphQLRepositoryOptions,
    GraphQLRepositorySelectorOptions,
)
from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient


TEST_REPOS = [
    {
        "id": 1,
        "name": "repo1",
        "full_name": "test-org/repo1",
        "description": "Test repository 1",
    },
    {
        "id": 2,
        "name": "repo2",
        "full_name": "test-org/repo2",
        "description": "Test repository 2",
    },
]

TEST_GRAPHQL_REPO = {
    "id": "MDEwOlJlcG9zaXRvcnkx",
    "name": "repo1",
    "nameWithOwner": "test-org/repo1",
    "description": "Test repository 1",
    "url": "https://github.com/test-org/repo1",
    "homepageUrl": None,
    "isPrivate": False,
    "createdAt": "2023-01-01T00:00:00Z",
    "updatedAt": "2023-01-02T00:00:00Z",
    "pushedAt": "2023-01-03T00:00:00Z",
    "defaultBranchRef": {"name": "main"},
    "languages": {"nodes": [{"name": "Python"}]},
    "visibility": "PUBLIC",
    "collaborators": {
        "nodes": [
            {"login": "user1", "roleName": "ADMIN"},
            {"login": "user2", "roleName": "WRITE"},
        ]
    },
}

TEST_GRAPHQL_REPOS = [
    {
        "id": "MDEwOlJlcG9zaXRvcnkx",
        "name": "repo1",
        "nameWithOwner": "test-org/repo1",
        "description": "Test repository 1",
        "visibility": "PUBLIC",
        "collaborators": {"nodes": []},
    },
    {
        "id": "MDEwOlJlcG9zaXRvcnky",
        "name": "repo2",
        "nameWithOwner": "test-org/repo2",
        "description": "Test repository 2",
        "visibility": "PRIVATE",
        "collaborators": {"nodes": []},
    },
]

TEST_TEAMS = [
    {"id": 1, "name": "team1", "slug": "team1"},
    {"id": 2, "name": "team2", "slug": "team2"},
]

TEST_CUSTOM_PROPERTIES = [
    {"property_name": "prop1", "value": "value1"},
    {"property_name": "prop2", "value": "value2"},
]


@pytest.mark.asyncio
class TestRestRepositoryExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_REPOS[0]

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            repo = await exporter.get_resource(SingleRepositoryOptions(name="repo1"))

            assert repo == TEST_REPOS[0]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test repos
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    type=mock_port_app_config.repository_type
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/{rest_client.organization}/repos",
                    {"type": "all"},
                )


class TestGraphQLRepositoryExporter:
    @pytest.mark.asyncio
    async def test_get_resource_basic(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting a single repository without enrichment."""
        mock_response = {
            "data": {"organization": {"repository": TEST_GRAPHQL_REPO.copy()}}
        }

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = SingleGraphQLRepositoryOptions(
            name="repo1",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=False,
                custom_properties=False,
            ),
        )

        with patch.object(
            graphql_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            repo = await exporter.get_resource(options)

            # Check that the repository was normalized (visibility converted to lowercase)
            assert repo["visibility"] == "public"
            assert repo["collaborators"] == [
                {"login": "user1", "roleName": "ADMIN"},
                {"login": "user2", "roleName": "WRITE"},
            ]

            # Verify the GraphQL payload was built correctly
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["method"] == "POST"
            assert (
                call_args[1]["json_data"]["variables"]["organization"]
                == graphql_client.organization
            )
            assert call_args[1]["json_data"]["variables"]["repositoryName"] == "repo1"

    @pytest.mark.asyncio
    async def test_get_resource_with_teams_enrichment(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting a repository with teams enrichment."""
        mock_response = {
            "data": {"organization": {"repository": TEST_GRAPHQL_REPO.copy()}}
        }

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = SingleGraphQLRepositoryOptions(
            name="repo1",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=True,
                custom_properties=False,
            ),
        )

        with (
            patch.object(
                graphql_client, "send_api_request", new_callable=AsyncMock
            ) as mock_graphql_request,
            patch(
                "github.core.exporters.repository_exporter.create_github_client"
            ) as mock_create_client,
        ):
            mock_graphql_request.return_value = mock_response

            # Mock the REST client for enrichment
            mock_rest_client = MagicMock()
            mock_create_client.return_value = mock_rest_client
            mock_rest_client.send_api_request = AsyncMock(return_value=TEST_TEAMS)

            repo = await exporter.get_resource(options)

            # Check that teams were added
            assert repo["teams"] == TEST_TEAMS
            assert repo["visibility"] == "public"

            # Verify REST client was called for teams
            mock_rest_client.send_api_request.assert_called_once_with(
                f"{mock_rest_client.base_url}/repos/{mock_rest_client.organization}/repo1/teams"
            )

    @pytest.mark.asyncio
    async def test_get_resource_with_custom_properties_enrichment(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting a repository with custom properties enrichment."""
        mock_response = {
            "data": {"organization": {"repository": TEST_GRAPHQL_REPO.copy()}}
        }

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = SingleGraphQLRepositoryOptions(
            name="repo1",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=False,
                custom_properties=True,
            ),
        )

        with (
            patch.object(
                graphql_client, "send_api_request", new_callable=AsyncMock
            ) as mock_graphql_request,
            patch(
                "github.core.exporters.repository_exporter.create_github_client"
            ) as mock_create_client,
        ):
            mock_graphql_request.return_value = mock_response

            # Mock the REST client for enrichment
            mock_rest_client = MagicMock()
            mock_create_client.return_value = mock_rest_client
            mock_rest_client.send_api_request = AsyncMock(
                return_value=TEST_CUSTOM_PROPERTIES
            )

            repo = await exporter.get_resource(options)

            # Check that custom properties were added
            assert repo["customProperties"] == TEST_CUSTOM_PROPERTIES

            # Verify REST client was called for custom properties
            mock_rest_client.send_api_request.assert_called_once_with(
                f"{mock_rest_client.base_url}/repos/{mock_rest_client.organization}/repo1/properties/values"
            )

    @pytest.mark.asyncio
    async def test_get_resource_with_all_enrichments(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting a repository with all enrichments enabled."""
        mock_response = {
            "data": {"organization": {"repository": TEST_GRAPHQL_REPO.copy()}}
        }

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = SingleGraphQLRepositoryOptions(
            name="repo1",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=True,
                teams=True,
                custom_properties=True,
            ),
        )

        with (
            patch.object(
                graphql_client, "send_api_request", new_callable=AsyncMock
            ) as mock_graphql_request,
            patch(
                "github.core.exporters.repository_exporter.create_github_client"
            ) as mock_create_client,
        ):
            mock_graphql_request.return_value = mock_response

            # Mock the REST client for enrichment
            mock_rest_client = MagicMock()
            mock_create_client.return_value = mock_rest_client
            mock_rest_client.send_api_request = AsyncMock()
            mock_rest_client.send_api_request.side_effect = [
                TEST_TEAMS,
                TEST_CUSTOM_PROPERTIES,
            ]

            repo = await exporter.get_resource(options)

            # Check that all enrichments were added
            assert repo["teams"] == TEST_TEAMS
            assert repo["customProperties"] == TEST_CUSTOM_PROPERTIES
            assert repo["collaborators"] == [
                {"login": "user1", "roleName": "ADMIN"},
                {"login": "user2", "roleName": "WRITE"},
            ]

            # Verify REST client was called for both enrichments
            assert mock_rest_client.send_api_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_resource_empty_response(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test handling empty response from GraphQL."""
        exporter = GraphQLRepositoryExporter(graphql_client)
        options = SingleGraphQLRepositoryOptions(
            name="repo1",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=False,
                custom_properties=False,
            ),
        )

        with patch.object(
            graphql_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = None
            repo = await exporter.get_resource(options)

            assert repo == {}

    @pytest.mark.asyncio
    async def test_get_paginated_resources_basic(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting paginated repositories without enrichment."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_GRAPHQL_REPOS

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = ListGraphQLRepositoryOptions(
            type="all",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=False,
                custom_properties=False,
            ),
        )

        with patch.object(
            graphql_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2

                # Check that repositories were normalized
                assert repos[0][0]["visibility"] == "public"
                assert repos[0][1]["visibility"] == "private"

                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert (
                    "query" in call_args[0][0]
                )  # The GraphQL query should contain "query"
                assert (
                    call_args[1]["params"]["organization"]
                    == graphql_client.organization
                )
                assert call_args[1]["params"]["__path"] == "organization.repositories"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_enrichments(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting paginated repositories with enrichments."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_GRAPHQL_REPOS

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = ListGraphQLRepositoryOptions(
            type="all",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=True,
                teams=True,
                custom_properties=True,
            ),
        )

        with (
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch(
                "github.core.exporters.repository_exporter.create_github_client"
            ) as mock_create_client,
        ):
            # Mock the REST client for enrichment
            mock_rest_client = MagicMock()
            mock_create_client.return_value = mock_rest_client
            mock_rest_client.send_api_request = AsyncMock()
            mock_rest_client.send_api_request.side_effect = [
                TEST_TEAMS,
                TEST_CUSTOM_PROPERTIES,  # For repo1
                TEST_TEAMS,
                TEST_CUSTOM_PROPERTIES,  # For repo2
            ]

            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2

                # Check that enrichments were added to both repositories
                for repo in repos[0]:
                    assert repo["teams"] == TEST_TEAMS
                    assert repo["customProperties"] == TEST_CUSTOM_PROPERTIES

                # Verify REST client was called for each repository (2 repos * 2 enrichments each)
                assert mock_rest_client.send_api_request.call_count == 4

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_visibility_filter(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test getting paginated repositories with visibility filter."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_GRAPHQL_REPOS

        exporter = GraphQLRepositoryExporter(graphql_client)
        options = ListGraphQLRepositoryOptions(
            type="private",
            selector=GraphQLRepositorySelectorOptions(
                collaborators=False,
                teams=False,
                custom_properties=False,
            ),
        )

        with patch.object(
            graphql_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                # Verify the returned data
                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_GRAPHQL_REPOS

                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[1]["params"]["repositoryVisibility"] == "PRIVATE"

    def test_build_optional_graphql_fields_from_selector(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test building optional GraphQL fields from selector."""
        exporter = GraphQLRepositoryExporter(graphql_client)

        # Test with collaborators enabled
        selector: GraphQLRepositorySelectorOptions = GraphQLRepositorySelectorOptions(
            collaborators=True,
            teams=False,
            custom_properties=False,
        )
        fields = exporter._build_optional_graphql_fields_from_selector(selector)
        assert "collaborators" in fields

        # Test with no fields enabled
        selector = GraphQLRepositorySelectorOptions(
            collaborators=False,
            teams=False,
            custom_properties=False,
        )
        fields = exporter._build_optional_graphql_fields_from_selector(selector)
        assert fields == ""

    def test_combine_repository_fields(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test combining repository fields."""
        exporter = GraphQLRepositoryExporter(graphql_client)

        fields = exporter._combine_repository_fields("field1", "field2", "field3")
        assert fields == "field1\nfield2\nfield3"

    def test_normalize_repository(self, graphql_client: GithubGraphQLClient) -> None:
        """Test repository normalization."""
        exporter = GraphQLRepositoryExporter(graphql_client)

        # Test visibility normalization
        repo: dict[str, Any] = {"visibility": "PUBLIC", "name": "test"}
        normalized = exporter._normalize_repository(repo)
        assert normalized["visibility"] == "public"

        # Test collaborators normalization
        repo = {"name": "test", "collaborators": {"nodes": [{"login": "user1"}]}}
        normalized = exporter._normalize_repository(repo)
        assert normalized["collaborators"] == [{"login": "user1"}]

        # Test collaborators already normalized
        repo = {"name": "test", "collaborators": [{"login": "user1"}]}
        normalized = exporter._normalize_repository(repo)
        assert normalized["collaborators"] == [{"login": "user1"}]
