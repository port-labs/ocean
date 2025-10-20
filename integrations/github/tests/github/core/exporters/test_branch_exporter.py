from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.branch_exporter import RestBranchExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleBranchOptions, ListBranchOptions
from github.clients.http.rest_client import GithubRestClient


TEST_BRANCHES = [
    {
        "name": "main",
        "commit": {
            "sha": "abc123",
            "url": "https://api.github.com/repos/test-org/repo1/commits/abc123",
        },
        "protected": True,
    },
    {
        "name": "develop",
        "commit": {
            "sha": "def456",
            "url": "https://api.github.com/repos/test-org/repo1/commits/def456",
        },
        "protected": False,
    },
]


@pytest.mark.asyncio
class TestRestBranchExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_BRANCHES[0]

        exporter = RestBranchExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            branch = await exporter.get_resource(
                SingleBranchOptions(
                    organization="test-org",
                    repo_name="repo1",
                    branch_name="main",
                    protection_rules=False,
                )
            )

            assert branch["__repository"] == "repo1"  # Check repository is enriched
            assert branch["name"] == "main"  # Check name is preserved

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1/branches/main"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test branches
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_BRANCHES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListBranchOptions(
                    organization="test-org",
                    repo_name="repo1",
                    protection_rules=False,
                    detailed=False,
                )
                exporter = RestBranchExporter(rest_client)

                branches: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(branches) == 1
                assert len(branches[0]) == 2

                # Check each branch is properly enriched
                for branch in branches[0]:
                    assert "__repository" in branch

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/repo1/branches",
                    {},
                )

    async def test_get_resource_with_protection_rules(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestBranchExporter(rest_client)

        # First call returns branch payload; enrichment merges protection rules
        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_BRANCHES[0]

            # Patch the enrichment method to attach rules (unit test scope)
            with patch.object(
                exporter,
                "_enrich_branch_with_protection_rules",
                new_callable=AsyncMock,
            ) as mock_enrich:
                enriched = {**TEST_BRANCHES[0], "__protection_rules": {"enabled": True}}
                mock_enrich.return_value = enriched

                branch = await exporter.get_resource(
                    SingleBranchOptions(
                        organization="test-org",
                        repo_name="repo1",
                        branch_name="main",
                        protection_rules=True,
                    )
                )

                assert branch["__repository"] == "repo1"
                assert branch["name"] == "main"
                assert branch["__protection_rules"] == {"enabled": True}
                mock_enrich.assert_awaited_once()

    async def test_get_paginated_resources_detailed(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_BRANCHES

        exporter = RestBranchExporter(rest_client)

        # Mock get_resource to simulate detailed hydration
        async def fake_fetch_branch(
            repo_name: str, branch_name: str, organization: str
        ) -> dict[str, Any]:
            # Return a shape that differs from list payload to ensure replacement happened
            return {"name": branch_name, "commit": {"sha": "zzz"}, "_links": {}}

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch.object(exporter, "fetch_branch", side_effect=fake_fetch_branch),
        ):
            async with event_context("test_event"):
                options = ListBranchOptions(
                    organization="test-org",
                    repo_name="repo1",
                    detailed=True,
                    protection_rules=False,
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                result = batches[0]
                # get_resource should have been called for each branch (detail=True present)
                assert all(isinstance(b.get("_links"), dict) for b in result)
                # still enriched with repository
                assert all(b.get("__repository") == "repo1" for b in result)

    async def test_get_paginated_resources_protection_rules(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_BRANCHES

        exporter = RestBranchExporter(rest_client)

        async def fake_enrich(
            repo_name: str, branch: dict[str, Any], organization: str
        ) -> dict[str, Any]:
            return {**branch, "__protection_rules": {"enabled": True}}

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch.object(
                exporter,
                "_enrich_branch_with_protection_rules",
                side_effect=fake_enrich,
            ),
        ):
            async with event_context("test_event"):
                options = ListBranchOptions(
                    organization="test-org",
                    repo_name="repo1",
                    detailed=False,
                    protection_rules=True,
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                result = batches[0]
                assert all(
                    b.get("__protection_rules") == {"enabled": True} for b in result
                )
                assert all(b.get("__repository") == "repo1" for b in result)

    async def test_get_paginated_resources_detailed_and_protection_rules(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_BRANCHES

        exporter = RestBranchExporter(rest_client)

        async def fake_fetch_branch(
            repo_name: str, branch_name: str, organization: str
        ) -> dict[str, Any]:
            return {"name": branch_name, "_links": {}}

        async def fake_enrich(
            repo_name: str, branch: dict[str, Any], organization: str
        ) -> dict[str, Any]:
            # ensure we see the detailed branch passed in
            assert isinstance(branch.get("_links"), dict)
            return {**branch, "__protection_rules": {"enabled": True}}

        with (
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
            patch.object(exporter, "fetch_branch", side_effect=fake_fetch_branch),
            patch.object(
                exporter,
                "_enrich_branch_with_protection_rules",
                side_effect=fake_enrich,
            ),
        ):
            async with event_context("test_event"):
                options = ListBranchOptions(
                    organization="test-org",
                    repo_name="repo1",
                    detailed=True,
                    protection_rules=True,
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                result = batches[0]
                assert all(isinstance(b.get("_links"), dict) for b in result)
                assert all(
                    b.get("__protection_rules") == {"enabled": True} for b in result
                )
                assert all(b.get("__repository") == "repo1" for b in result)
