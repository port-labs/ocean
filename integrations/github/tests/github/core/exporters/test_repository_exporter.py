from datetime import datetime, timezone
from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.repository_exporter import (
    ARCHIVED_QUALIFIER_PATTERN,
    ENRICHMENT_BATCH_SIZE,
    RestRepositoryExporter,
)
from pydantic.v1 import ValidationError
from github.core.options import ListRepositoryOptions, SingleRepositoryOptions
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from port_ocean.core.incremental.cursor_context import with_active_incremental_cursor
from github.helpers.models import RepoSearchParams
from github.clients.http.rest_client import GithubRestClient
from integration import GithubRepositorySelector
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator

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

TEST_REPOS_WITH_ARCHIVED = [
    {
        "id": 1,
        "name": "active-repo",
        "full_name": "test-org/active-repo",
        "archived": False,
    },
    {
        "id": 2,
        "name": "archived-repo",
        "full_name": "test-org/archived-repo",
        "archived": True,
    },
]

TEST_COLLABORATORS = [
    {
        "id": 101,
        "login": "user1",
        "type": "User",
    },
    {
        "id": 102,
        "login": "user2",
        "type": "User",
    },
]

TEST_PAGES = {
    "url": "https://api.github.com/repos/test-org/repo1/pages",
    "status": "built",
    "cname": "example.com",
    "custom_404": False,
    "html_url": "https://test-org.github.io/repo1/",
    "source": {"branch": "main", "path": "/docs"},
    "public": True,
}


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
            repo = await exporter.get_resource(
                SingleRepositoryOptions(organization="test-org", name="repo1")
            )

            assert repo == TEST_REPOS[0]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1"
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
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org/repos",
                    {"type": "all"},
                )

    async def test_get_paginated_resources_with_included_relationships(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create a mock that returns different data based on the URL
        async def mock_paginated_request(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "collaborators" in url:
                yield TEST_COLLABORATORS
            else:
                yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    included_relations={"collaborators": {"include": True}},
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2

                # Verify that repositories are enriched with collaborators
                for repo in repos[0]:
                    assert "__collaborators" in repo
                    assert repo["__collaborators"] == TEST_COLLABORATORS
                    # Verify original repository data is preserved
                    assert "id" in repo
                    assert "name" in repo
                    assert "full_name" in repo
                    assert "description" in repo

                # Verify the main repository request was called
                mock_request.assert_any_call(
                    f"{rest_client.base_url}/orgs/test-org/repos",
                    {"type": "all"},
                )

                # Verify collaborator requests were called for each repository
                expected_collaborator_calls: list[tuple[str, dict[str, Any]]] = [
                    (
                        f"{rest_client.base_url}/repos/test-org/repo1/collaborators",
                        {"affiliation": "all"},
                    ),
                    (
                        f"{rest_client.base_url}/repos/test-org/repo2/collaborators",
                        {"affiliation": "all"},
                    ),
                ]

                # Should have 3 total calls: 1 for repositories + 2 for collaborators
                assert mock_request.call_count == 3
                mock_request.assert_any_call(*expected_collaborator_calls[0])
                mock_request.assert_any_call(*expected_collaborator_calls[1])

    async def test_get_paginated_resources_with_pages_relationship(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        repos = [repo.copy() for repo in TEST_REPOS]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield repos

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_paginated_request,
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_api_request,
        ):
            mock_api_request.return_value = TEST_PAGES.copy()

            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    included_relations={"pages": {"include": True}},
                )
                exporter = RestRepositoryExporter(rest_client)

                repos_with_pages: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos_with_pages) == 1
                assert len(repos_with_pages[0]) == 2
                assert all(
                    repo["__pages"] == TEST_PAGES for repo in repos_with_pages[0]
                )

                mock_paginated_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org/repos",
                    {"type": "all"},
                )
                assert mock_api_request.call_count == 2
                mock_api_request.assert_any_call(
                    f"{rest_client.base_url}/repos/test-org/repo1/pages"
                )
                mock_api_request.assert_any_call(
                    f"{rest_client.base_url}/repos/test-org/repo2/pages"
                )

    async def test_get_paginated_resources_with_pages_relationship_empty_response(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        repos = [repo.copy() for repo in TEST_REPOS]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield repos

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_api_request,
            patch(
                "github.core.exporters.repository_exporter.logger.warning"
            ) as mock_warning,
        ):
            mock_api_request.return_value = {}

            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    included_relations={"pages": {"include": True}},
                )
                exporter = RestRepositoryExporter(rest_client)

                repos_with_pages: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos_with_pages) == 1
                assert all(repo["__pages"] == {} for repo in repos_with_pages[0])
                mock_warning.assert_not_called()

    async def test_get_paginated_resources_with_search_params(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            if "search" in url:
                yield {"items": TEST_REPOS}
            else:
                yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name"),
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {"q": "org:test-org code in:name"},
                )

    async def test_get_paginated_resources_excludes_archived_repositories_list_strategy(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS_WITH_ARCHIVED

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    exclude_archived=True,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == ["active-repo"]

    async def test_get_paginated_resources_excludes_archived_repositories_search_strategy(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            if "search" in url:
                yield {"items": TEST_REPOS_WITH_ARCHIVED}
            else:
                yield TEST_REPOS_WITH_ARCHIVED

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name"),
                    exclude_archived=True,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == ["active-repo"]

    async def test_search_strategy_appends_archived_false_qualifier_when_enabled(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """When exclude_archived is enabled and repoSearch has no archived:
        qualifier, archived:false is appended to the search query to reduce
        wasted search pages/rate limit usage. The client-side filter (see
        above) remains the safety net regardless."""

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            yield {"items": TEST_REPOS_WITH_ARCHIVED}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name"),
                    exclude_archived=True,
                )
                exporter = RestRepositoryExporter(rest_client)

                [batch async for batch in exporter.get_paginated_resources(options)]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {"q": "org:test-org code in:name archived:false"},
                )

    async def test_search_strategy_overrides_conflicting_archived_qualifier_when_enabled(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """excludeArchived is an explicit selector-level opt-in, so it takes
        precedence over a conflicting archived:true qualifier a user has set
        directly in repoSearch: the query qualifier is overridden, and the
        client-side filter still excludes any archived repo that comes
        back."""

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            yield {"items": TEST_REPOS_WITH_ARCHIVED}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name archived:true"),
                    exclude_archived=True,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {"q": "org:test-org code in:name archived:false"},
                )
                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == ["active-repo"]

    async def test_search_strategy_leaves_query_untouched_when_exclude_archived_disabled(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """exclude_archived defaults to False, so an explicit archived:true
        qualifier in repoSearch passes through unchanged - nothing is
        overridden when the feature is off, and archived repos are still
        returned (backward compatible)."""

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            yield {"items": TEST_REPOS_WITH_ARCHIVED}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name archived:true"),
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {"q": "org:test-org code in:name archived:true"},
                )
                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == [
                    "active-repo",
                    "archived-repo",
                ]

    async def test_search_strategy_appends_archived_false_alongside_forced_qualifiers(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """When the search strategy runs without an explicit repoSearch (e.g.
        GitHub App auth against a personal account), exclude_archived still
        appends archived:false alongside the forced qualifiers."""
        from github.clients.auth.github_app.installation_authenticator import (
            GitHubAppInstallationAuthenticator,
        )

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            yield {"items": TEST_REPOS_WITH_ARCHIVED}

        # rest_client is a process-wide cached instance (keyed by rate limit
        # scope), so the authenticator swap below must be reverted afterward
        # to avoid leaking App-auth state into other tests.
        original_authenticator = rest_client.authenticator
        try:
            with patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request:
                rest_client.authenticator = GitHubAppInstallationAuthenticator(
                    app_auth=GitHubAppAuthenticator(
                        app_id="app",
                        private_key="key",
                        github_host=rest_client.base_url,
                    ),
                    organization="test-org",
                    installation_id="123",
                )

                async with event_context("test_event"):
                    options = ListRepositoryOptions(
                        organization="test-org",
                        organization_type="User",
                        type=mock_port_app_config.repository_type,
                        exclude_archived=True,
                    )
                    exporter = RestRepositoryExporter(rest_client)

                    [batch async for batch in exporter.get_paginated_resources(options)]

                    mock_request.assert_called_once_with(
                        f"{rest_client.base_url}/search/repositories",
                        {"q": "org:test-org fork:true is:all archived:false"},
                    )
        finally:
            rest_client.authenticator = original_authenticator

    async def test_get_paginated_resources_keeps_archived_repositories_by_default(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """`exclude_archived` defaults to False, so archived repos are still returned."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS_WITH_ARCHIVED

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == [
                    "active-repo",
                    "archived-repo",
                ]

    async def test_search_strategy_applies_incremental_cursor(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        cursor = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mixed_repos = [
            {"id": 1, "name": "fresh-repo", "updated_at": "2026-06-02T00:00:00Z"},
            {"id": 2, "name": "stale-repo", "updated_at": "2026-05-01T00:00:00Z"},
        ]

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            yield {"items": mixed_repos}
            yield {"items": mixed_repos}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(query="code in:name"),
                )
                exporter = RestRepositoryExporter(rest_client)

                with with_active_incremental_cursor(cursor):
                    repos: list[list[dict[str, Any]]] = [
                        batch
                        async for batch in exporter.get_paginated_resources(options)
                    ]

                assert len(repos) == 1
                assert [repo["name"] for repo in repos[0]] == ["fresh-repo"]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {
                        "q": "org:test-org code in:name",
                        "sort": "updated",
                        "order": "desc",
                    },
                )

    async def test_get_paginated_resources_user_context_builds_user_repos_url(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-user",
                    organization_type="User",
                    type=mock_port_app_config.repository_type,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/repos",
                    {"affiliation": "owner", "visibility": "all"},
                )

    async def test_get_paginated_resources_uses_search_strategy_when_app_auth_and_personal_account(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        from github.clients.auth.github_app.installation_authenticator import (
            GitHubAppInstallationAuthenticator,
        )

        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            if "search" in url:
                yield {"items": TEST_REPOS}
            else:
                yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            # Force the exporter to detect App authentication
            rest_client.authenticator = GitHubAppInstallationAuthenticator(
                app_auth=GitHubAppAuthenticator(
                    app_id="app", private_key="key", github_host=rest_client.base_url
                ),
                organization="test-org",
                installation_id="123",
            )

            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="User",
                    type=mock_port_app_config.repository_type,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {"q": "org:test-org fork:true is:all"},
                )

    async def test_enrich_custom_properties_fetches_when_missing(
        self, rest_client: GithubRestClient
    ) -> None:
        repository: dict[str, Any] = {"name": "my-repo"}
        api_response = [
            {"property_name": "team", "value": "backend"},
            {"property_name": "environment", "value": "production"},
        ]

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = api_response
            result = await exporter._enrich_repository_with_custom_properties(
                repository, "test-org", {"include": True}
            )

            assert result["custom_properties"] == {
                "team": "backend",
                "environment": "production",
            }
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/my-repo/properties/values"
            )

    async def test_enrich_custom_properties_skips_when_already_present(
        self, rest_client: GithubRestClient
    ) -> None:
        repository: dict[str, Any] = {
            "name": "my-repo",
            "custom_properties": {"team": "frontend"},
        }

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            result = await exporter._enrich_repository_with_custom_properties(
                repository, "test-org", {"include": True}
            )

            assert result["custom_properties"] == {"team": "frontend"}
            mock_request.assert_not_called()

    async def test_enrich_custom_properties_sets_empty_dict_when_api_returns_empty(
        self, rest_client: GithubRestClient
    ) -> None:
        repository: dict[str, Any] = {"name": "my-repo"}

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = []
            result = await exporter._enrich_repository_with_custom_properties(
                repository, "test-org", {"include": True}
            )

            assert result["custom_properties"] == {}

    async def test_enrichment_batches_at_most_batch_size_repos(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """When exactly ENRICHMENT_BATCH_SIZE repos are returned, they should
        all be enriched in a single gather call of that size."""
        repos = [
            {"id": i, "name": f"repo{i}", "full_name": f"test-org/repo{i}"}
            for i in range(ENRICHMENT_BATCH_SIZE)
        ]

        gather_call_sizes: list[int] = []
        original_gather = __import__("asyncio").gather

        async def tracking_gather(*coros_or_futures: Any) -> Any:
            gather_call_sizes.append(len(coros_or_futures))
            return await original_gather(*coros_or_futures)

        async def mock_paginated_request(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "collaborators" in url:
                yield TEST_COLLABORATORS
            else:
                yield repos

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch("asyncio.gather", side_effect=tracking_gather),
        ):
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    included_relations={"collaborators": {"include": True}},
                )
                exporter = RestRepositoryExporter(rest_client)

                batches: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                assert len(batches[0]) == ENRICHMENT_BATCH_SIZE
                assert gather_call_sizes == [ENRICHMENT_BATCH_SIZE]

    async def test_enrichment_splits_when_exceeding_batch_size(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """When more than ENRICHMENT_BATCH_SIZE repos are returned, they should
        be split into multiple gather calls of at most ENRICHMENT_BATCH_SIZE."""
        total_repos = ENRICHMENT_BATCH_SIZE + 5
        repos = [
            {"id": i, "name": f"repo{i}", "full_name": f"test-org/repo{i}"}
            for i in range(total_repos)
        ]

        gather_call_sizes: list[int] = []
        original_gather = __import__("asyncio").gather

        async def tracking_gather(*coros_or_futures: Any) -> Any:
            gather_call_sizes.append(len(coros_or_futures))
            return await original_gather(*coros_or_futures)

        async def mock_paginated_request(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "collaborators" in url:
                yield TEST_COLLABORATORS
            else:
                yield repos

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch("asyncio.gather", side_effect=tracking_gather),
        ):
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    organization_type="Organization",
                    type=mock_port_app_config.repository_type,
                    included_relations={"collaborators": {"include": True}},
                )
                exporter = RestRepositoryExporter(rest_client)

                batches: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 2
                assert len(batches[0]) == ENRICHMENT_BATCH_SIZE
                assert len(batches[1]) == 5

                assert all(size <= ENRICHMENT_BATCH_SIZE for size in gather_call_sizes)
                assert gather_call_sizes == [ENRICHMENT_BATCH_SIZE, 5]

                total_enriched = sum(len(b) for b in batches)
                assert total_enriched == total_repos


def test_normalized_relations_from_included_relations_alias() -> None:
    selector = GithubRepositorySelector.parse_obj(
        {
            "query": "true",
            "includedRelations": {
                "teams": True,
                "sbom": False,
                "pages": True,
                "collaborators": {"affiliation": "direct"},
            },
        }
    )

    assert selector.normalized_relations == {
        "teams": {"include": True},
        "pages": {"include": True},
        "collaborators": {"include": True, "affiliation": "direct"},
    }


def test_included_relations_cannot_be_supplied_with_include() -> None:
    with pytest.raises(ValidationError) as exc:
        GithubRepositorySelector.parse_obj(
            {
                "query": "true",
                "include": ["teams"],
                "includedRelations": {"collaborators": {"affiliation": "all"}},
            }
        )

    assert "You cannot supply both 'include' and 'includedRelations'" in str(exc.value)


def test_normalized_relations_falls_back_to_include_list() -> None:
    selector = GithubRepositorySelector.parse_obj(
        {"query": "true", "include": ["teams", "sbom"]}
    )

    assert selector.normalized_relations == {
        "teams": {"include": True},
        "sbom": {"include": True},
    }


def test_included_relations_forbids_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        GithubRepositorySelector.parse_obj(
            {"query": "true", "includedRelations": {"unknown": True}}
        )


@pytest.mark.parametrize(
    "query,should_match",
    [
        ("archived:true", True),
        ("archived:false", True),
        ("ARCHIVED:TRUE", True),
        ("code in:name archived:true", True),
        ("archived:true code in:name", True),
        ("fork:true is:all", False),
        ("", False),
        # A substring that merely contains "archived:" as part of another
        # token must not be mistaken for the qualifier.
        ("unarchived:true", False),
    ],
)
def test_archived_qualifier_pattern_matches_standalone_qualifier_only(
    query: str, should_match: bool
) -> None:
    assert bool(ARCHIVED_QUALIFIER_PATTERN.search(query)) is should_match
