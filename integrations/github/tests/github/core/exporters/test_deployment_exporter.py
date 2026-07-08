from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context


TEST_DEPLOYMENTS = [
    {
        "id": 123,
        "environment": "production",
        "ref": "main",
        "sha": "abc123",
        "description": "Deploy to production",
        "url": "https://github.com/org/repo/deployments/123",
        "created_at": "2024-03-20T10:00:00Z",
        "transient_environment": False,
        "production_environment": True,
    },
    {
        "id": 124,
        "environment": "production",
        "ref": "main",
        "sha": "def456",
        "description": "Deploy to production",
        "url": "https://github.com/org/repo/deployments/124",
        "created_at": "2024-03-20T11:00:00Z",
        "transient_environment": False,
        "production_environment": True,
    },
]


@pytest.mark.asyncio
class TestRestDeploymentExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_DEPLOYMENTS[0]

        exporter = RestDeploymentExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            deployment = await exporter.get_resource(
                SingleDeploymentOptions(
                    organization="test-org", repo_name="test-repo", id="123"
                )
            )

            assert deployment == {
                **TEST_DEPLOYMENTS[0],
                "__repository": "test-repo",
                "__organization": "test-org",
            }

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/deployments/123"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test deployments
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_DEPLOYMENTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListDeploymentsOptions(
                    organization="test-org", repo_name="test-repo"
                )
                exporter = RestDeploymentExporter(rest_client)

                deployments: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(deployments) == 1
                assert len(deployments[0]) == 2
                assert all(
                    "__repository" in deployment for deployment in deployments[0]
                )
                assert all(
                    deployment["__repository"] == "test-repo"
                    for deployment in deployments[0]
                )
                assert all(
                    deployment["__organization"] == "test-org"
                    for deployment in deployments[0]
                )

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/deployments",
                    {},
                )

    async def test_get_paginated_resources_enriches_first_commit(
        self, rest_client: GithubRestClient
    ) -> None:
        deployments = [
            {
                "id": 1,
                "environment": "production",
                "sha": "deploy_new",
                "created_at": "2024-03-20T11:00:00Z",
            },
            {
                "id": 2,
                "environment": "production",
                "sha": "deploy_old",
                "created_at": "2024-03-20T10:00:00Z",
            },
        ]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield deployments

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if "/compare/" in resource:
                return {
                    "files": [],
                    "total_commits": 2,
                    "commits": [
                        {
                            "sha": "commit_late",
                            "commit": {"committer": {"date": "2024-03-20T10:50:00Z"}},
                        },
                        {
                            "sha": "commit_early",
                            "commit": {"committer": {"date": "2024-03-20T10:10:00Z"}},
                        },
                    ],
                }
            return {
                "sha": "deploy_old",
                "commit": {"committer": {"date": "2024-03-20T09:00:00Z"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        by_id = {deployment["id"]: deployment for deployment in collected}
        assert by_id[1]["__firstCommit"]["__sha"] == "commit_early"
        assert by_id[1]["__firstCommit"]["__timestamp"] == "2024-03-20T10:10:00Z"
        assert by_id[1]["__commitCount"] == 2
        assert "__commitCount" not in by_id[1]["__firstCommit"]
        assert by_id[2]["__firstCommit"]["__sha"] == "deploy_old"
        assert by_id[2]["__commitCount"] == 1

    async def test_get_paginated_resources_without_first_commit_skips_compare(
        self, rest_client: GithubRestClient
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_DEPLOYMENTS

        api_mock = AsyncMock()
        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(rest_client, "send_api_request", api_mock):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org", repo_name="test-repo"
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        assert all("__firstCommit" not in deployment for deployment in collected)
        api_mock.assert_not_called()

    async def test_first_commit_pairs_predecessor_regardless_of_order(
        self, rest_client: GithubRestClient
    ) -> None:
        # Deployments delivered oldest-first; pairing must still follow created_at order.
        deployments = [
            {
                "id": 2,
                "environment": "production",
                "sha": "deploy_old",
                "created_at": "2024-03-20T10:00:00Z",
            },
            {
                "id": 1,
                "environment": "production",
                "sha": "deploy_new",
                "created_at": "2024-03-20T11:00:00Z",
            },
        ]
        compared: list[str] = []

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield deployments

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if "/compare/" in resource:
                compared.append(resource)
                return {
                    "files": [],
                    "total_commits": 1,
                    "commits": [
                        {
                            "sha": "c1",
                            "commit": {"committer": {"date": "2024-03-20T10:30:00Z"}},
                        }
                    ],
                }
            return {
                "sha": "deploy_old",
                "commit": {"committer": {"date": "2024-03-20T09:00:00Z"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        # Exactly one compare, for the newer deployment against the older one's sha.
        assert len(compared) == 1
        assert "deploy_old...deploy_new" in compared[0]
        by_id = {deployment["id"]: deployment for deployment in collected}
        assert by_id[1]["__firstCommit"]["__sha"] == "c1"
        assert by_id[1]["__commitCount"] == 1

    async def test_first_commit_pairs_predecessor_across_pages(
        self, rest_client: GithubRestClient
    ) -> None:
        # Predecessor is delivered on a later page; pairing must still span pages.
        newer = {
            "id": 1,
            "environment": "production",
            "sha": "deploy_new",
            "created_at": "2024-03-20T11:00:00Z",
        }
        older = {
            "id": 2,
            "environment": "production",
            "sha": "deploy_old",
            "created_at": "2024-03-20T10:00:00Z",
        }
        compared: list[str] = []

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [newer]
            yield [older]

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if "/compare/" in resource:
                compared.append(resource)
                return {
                    "files": [],
                    "total_commits": 1,
                    "commits": [
                        {
                            "sha": "c1",
                            "commit": {"committer": {"date": "2024-03-20T10:30:00Z"}},
                        }
                    ],
                }
            return {
                "sha": "deploy_old",
                "commit": {"committer": {"date": "2024-03-20T09:00:00Z"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        # Newer deployment pairs against the older one delivered on the next page.
        assert len(compared) == 1
        assert "deploy_old...deploy_new" in compared[0]
        by_id = {deployment["id"]: deployment for deployment in collected}
        assert by_id[1]["__firstCommit"]["__sha"] == "c1"
        assert by_id[1]["__commitCount"] == 1

    async def test_first_commit_cross_page_multi_environment(
        self, rest_client: GithubRestClient
    ) -> None:
        # Each environment's predecessor lives on the next page; pairing must run per-env.
        page_one = [
            {
                "id": 1,
                "environment": "production",
                "sha": "prod_new",
                "created_at": "2024-03-20T11:00:00Z",
            },
            {
                "id": 2,
                "environment": "staging",
                "sha": "stg_new",
                "created_at": "2024-03-20T11:00:00Z",
            },
        ]
        page_two = [
            {
                "id": 3,
                "environment": "production",
                "sha": "prod_old",
                "created_at": "2024-03-20T10:00:00Z",
            },
            {
                "id": 4,
                "environment": "staging",
                "sha": "stg_old",
                "created_at": "2024-03-20T10:00:00Z",
            },
        ]
        compared: list[str] = []

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield page_one
            yield page_two

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if "/compare/" in resource:
                compared.append(resource)
                sha = (
                    "prod_commit" if "prod_old...prod_new" in resource else "stg_commit"
                )
                return {
                    "files": [],
                    "total_commits": 1,
                    "commits": [
                        {
                            "sha": sha,
                            "commit": {"committer": {"date": "2024-03-20T10:30:00Z"}},
                        }
                    ],
                }
            sha = resource.rsplit("/", 1)[-1]
            return {
                "sha": sha,
                "commit": {"committer": {"date": "2024-03-20T09:00:00Z"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        # Exactly two compares, one per environment.
        assert len(compared) == 2
        assert any("prod_old...prod_new" in url for url in compared)
        assert any("stg_old...stg_new" in url for url in compared)

        by_id = {deployment["id"]: deployment for deployment in collected}
        assert by_id[1]["__firstCommit"]["__sha"] == "prod_commit"
        assert by_id[1]["__commitCount"] == 1
        assert by_id[2]["__firstCommit"]["__sha"] == "stg_commit"
        assert by_id[2]["__commitCount"] == 1
        # Older deployments hit the single-commit fallback during flush.
        assert by_id[3]["__firstCommit"]["__sha"] == "prod_old"
        assert by_id[3]["__commitCount"] == 1
        assert by_id[4]["__firstCommit"]["__sha"] == "stg_old"
        assert by_id[4]["__commitCount"] == 1

    async def test_first_commit_skips_unparsable_timestamp(
        self, rest_client: GithubRestClient
    ) -> None:
        deployments = [
            {
                "id": 1,
                "environment": "production",
                "sha": "deploy_sha",
                "created_at": "2024-03-20T11:00:00Z",
            }
        ]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield deployments

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "sha": "deploy_sha",
                "commit": {"committer": {"date": "not-a-timestamp"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        assert collected[0].get("__firstCommit") is None
        assert "__commitCount" not in collected[0]

    async def test_first_commit_orders_by_time_not_string(
        self, rest_client: GithubRestClient
    ) -> None:
        deployments = [
            {
                "id": 1,
                "environment": "production",
                "sha": "deploy_new",
                "created_at": "2024-03-20T11:00:00Z",
            },
            {
                "id": 2,
                "environment": "production",
                "sha": "deploy_old",
                "created_at": "2024-03-20T10:00:00Z",
            },
        ]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield deployments

        def mock_api(resource: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if "/compare/" in resource:
                # Lexically "...00.5Z" < "...00Z", but 10:00:00 is the chronological earliest.
                return {
                    "files": [],
                    "total_commits": 2,
                    "commits": [
                        {
                            "sha": "commit_later",
                            "commit": {"committer": {"date": "2024-03-20T10:00:00.5Z"}},
                        },
                        {
                            "sha": "commit_earliest",
                            "commit": {"committer": {"date": "2024-03-20T10:00:00Z"}},
                        },
                    ],
                }
            return {
                "sha": "deploy_old",
                "commit": {"committer": {"date": "2024-03-20T09:00:00Z"}},
            }

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            with patch.object(
                rest_client,
                "send_api_request",
                new_callable=AsyncMock,
                side_effect=mock_api,
            ):
                async with event_context("test_event"):
                    options = ListDeploymentsOptions(
                        organization="test-org",
                        repo_name="test-repo",
                        enrich_with_first_commit=True,
                    )
                    exporter = RestDeploymentExporter(rest_client)
                    collected: list[dict[str, Any]] = []
                    async for batch in exporter.get_paginated_resources(options):
                        collected.extend(batch)

        by_id = {deployment["id"]: deployment for deployment in collected}
        assert by_id[1]["__firstCommit"]["__sha"] == "commit_earliest"
