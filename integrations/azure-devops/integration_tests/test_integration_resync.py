"""Integration tests for Azure DevOps resync.

Run with:
    pytest integration_tests/test_integration_resync.py -v
"""
import os
from typing import Any

import pytest
from port_ocean.integration_testing import BaseIntegrationTest, InterceptTransport, ResyncResult

# ── Fake constants ─────────────────────────────────────────────────────────────
_ORG = "test-org"
_BASE_URL = f"https://dev.azure.com/{_ORG}"
_PROJECT_ID = "aabbccdd-0001-0000-0000-000000000001"
_PROJECT_NAME = "test-project"
_TEAM_ID = "aabbccdd-0002-0000-0000-000000000001"
_BOARD_ID = "aabbccdd-0003-0000-0000-000000000001"
_REPO_ID = "aabbccdd-0004-0000-0000-000000000001"


class AzureDevOpsTransport:
    """Builds an InterceptTransport pre-loaded with minimal Azure DevOps API stubs.

    Subclass or extend by calling ``build()`` and adding more routes:

        transport = AzureDevOpsTransport.build()
        transport.add_route("GET", "/extra/path", {"json": {...}})

    Override class attributes to use different IDs across test modules.
    """

    org: str = _ORG
    base_url: str = _BASE_URL
    project_id: str = _PROJECT_ID
    project_name: str = _PROJECT_NAME
    team_id: str = _TEAM_ID
    board_id: str = _BOARD_ID
    repo_id: str = _REPO_ID

    @classmethod
    def build(cls) -> InterceptTransport:
        transport = InterceptTransport(strict=False)
        cls._add_project_routes(transport)
        cls._add_repository_routes(transport)
        cls._add_board_routes(transport)
        cls._add_work_item_routes(transport)
        cls._add_release_routes(transport)
        return transport

    # ── private builders ───────────────────────────────────────────────────────

    @classmethod
    def _project(cls) -> dict[str, Any]:
        return {
            "id": cls.project_id,
            "name": cls.project_name,
            "description": "Test project",
            "url": f"{cls.base_url}/_apis/projects/{cls.project_id}",
            "state": "wellFormed",
            "revision": 1,
            "visibility": "private",
            "lastUpdateTime": "2026-01-01T00:00:00.000Z",
        }

    @classmethod
    def _add_project_routes(cls, t: InterceptTransport) -> None:
        # Route patterns are substrings of the full URL (query params are appended by the
        # client). More-specific patterns are registered first so they win over broader ones.
        # Project teams  (most specific — contains UUID + /teams)
        t.add_route(
            "GET",
            f"/_apis/projects/{cls.project_id}/teams",
            {
                "status_code": 200,
                "json": {
                    "count": 1,
                    "value": [
                        {
                            "id": cls.team_id,
                            "name": f"{cls.project_name} Team",
                            "url": f"{cls.base_url}/_apis/projects/{cls.project_id}/teams/{cls.team_id}",
                            "description": "Default project team",
                            "projectName": cls.project_name,
                            "projectId": cls.project_id,
                        }
                    ],
                },
            },
        )
        # Project detail  (UUID-specific)
        t.add_route(
            "GET",
            f"/_apis/projects/{cls.project_id}",
            {
                "status_code": 200,
                "json": {
                    **cls._project(),
                    "_links": {
                        "self": {"href": f"{cls.base_url}/_apis/projects/{cls.project_id}"},
                        "collection": {"href": f"{cls.base_url}/_apis/projectCollections/collection-001"},
                        "web": {"href": f"{cls.base_url}/{cls.project_name}"},
                    },
                    "defaultTeam": {
                        "id": cls.team_id,
                        "name": f"{cls.project_name} Team",
                        "url": f"{cls.base_url}/_apis/projects/{cls.project_id}/teams/{cls.team_id}",
                    },
                },
            },
        )
        # Projects list  (most general — must be last)
        t.add_route(
            "GET",
            "/_apis/projects",
            {"status_code": 200, "json": {"count": 1, "value": [cls._project()]}},
        )

    @classmethod
    def _add_repository_routes(cls, t: InterceptTransport) -> None:
        t.add_route(
            "GET",
            f"/{cls.project_id}/_apis/git/repositories",
            {
                "status_code": 200,
                "json": {
                    "count": 1,
                    "value": [
                        {
                            "id": cls.repo_id,
                            "name": "test-repo",
                            "url": f"{cls.base_url}/{cls.project_id}/_apis/git/repositories/{cls.repo_id}",
                            "project": {
                                "id": cls.project_id,
                                "name": cls.project_name,
                                "state": "wellFormed",
                                "visibility": "private",
                            },
                            "defaultBranch": "refs/heads/main",
                            "size": 1024,
                            "remoteUrl": f"https://{cls.org}@dev.azure.com/{cls.org}/{cls.project_name}/_git/test-repo",
                            "webUrl": f"{cls.base_url}/{cls.project_name}/_git/test-repo",
                            "isDisabled": False,
                        }
                    ],
                },
            },
        )
        t.add_route(
            "GET",
            f"/{cls.project_id}/_apis/git/policy/configurations",
            {"status_code": 200, "json": {"count": 0, "value": []}},
        )

    @classmethod
    def _add_board_routes(cls, t: InterceptTransport) -> None:
        # Board detail first (more specific), board list last (broader substring).
        t.add_route(
            "GET",
            f"/{cls.project_id}/{cls.team_id}/_apis/work/boards/{cls.board_id}",
            {
                "status_code": 200,
                "json": {
                    "id": cls.board_id,
                    "url": f"{cls.base_url}/{cls.project_id}/{cls.team_id}/_apis/work/boards/{cls.board_id}",
                    "name": "Stories",
                    "revision": 1,
                    "columns": [
                        {
                            "id": "col-001",
                            "name": "New",
                            "itemLimit": 0,
                            "stateMappings": {"User Story": "New"},
                            "columnType": "incoming",
                        },
                        {
                            "id": "col-002",
                            "name": "Active",
                            "itemLimit": 5,
                            "stateMappings": {"User Story": "Active"},
                            "isSplit": False,
                            "description": "",
                            "columnType": "inProgress",
                        },
                        {
                            "id": "col-003",
                            "name": "Closed",
                            "itemLimit": 0,
                            "stateMappings": {"User Story": "Closed"},
                            "columnType": "outgoing",
                        },
                    ],
                    "rows": [{"id": "00000000-0000-0000-0000-000000000000", "name": None, "color": None}],
                    "isValid": True,
                    "canEdit": True,
                },
            },
        )
        # Board list  (broader substring — registered after board detail)
        t.add_route(
            "GET",
            f"/{cls.project_id}/_apis/work/boards",
            {
                "status_code": 200,
                "json": {
                    "count": 1,
                    "value": [
                        {
                            "id": cls.board_id,
                            "url": f"{cls.base_url}/{cls.project_id}/{cls.team_id}/_apis/work/boards/{cls.board_id}",
                            "name": "Stories",
                        }
                    ],
                },
            },
        )

    @classmethod
    def _add_work_item_routes(cls, t: InterceptTransport) -> None:
        t.add_route(
            "POST",
            f"/{cls.project_id}/_apis/wit/wiql",
            {
                "status_code": 200,
                "json": {
                    "queryType": "flat",
                    "queryResultType": "workItem",
                    "asOf": "2026-01-01T00:00:00.000Z",
                    "columns": [{"referenceName": "System.Id", "name": "ID"}],
                    "workItems": [],
                },
            },
        )

    @classmethod
    def _add_release_routes(cls, t: InterceptTransport) -> None:
        t.add_route(
            "GET",
            f"/{cls.project_id}/_apis/release/releases",
            {"status_code": 200, "json": {"count": 0, "value": []}},
        )


class TestResync(BaseIntegrationTest):
    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        return AzureDevOpsTransport.build()

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "resources": [
                {
                    "kind": "project",
                    "selector": {"query": "true", "defaultTeam": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": '.id | gsub(" "; "")',
                                "title": ".name",
                                "blueprint": '"azureDevopsProject"',
                                "properties": {
                                    "state": ".state",
                                    "revision": ".revision",
                                    "visibility": ".visibility",
                                    "defaultTeam": ".defaultTeam.name",
                                    "link": '.url | gsub("_apis/projects/"; "")',
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "repository",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"azureDevopsRepository"',
                                "properties": {"url": ".remoteUrl"},
                                "relations": {
                                    "project": '.project.id | gsub(" "; "")'
                                },
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-azure-devops",
                "type": "azure-devops",
                "config": {
                    "organization_url": f"https://dev.azure.com/{AzureDevOpsTransport.org}",
                    "personalAccessToken": "test-value",
                    "appHost": "https://placeholder.example.com",
                    "webhookSecret": "test-value",
                    "webhookAuthUsername": "test-value",
                },
            }
        }

    @pytest.mark.asyncio
    async def test_resync_creates_entities(self, resync: ResyncResult) -> None:
        """Smoke test: resync should produce entities without errors."""
        assert len(resync.errors) == 0, f"Resync had errors: {resync.errors}"
        assert len(resync.upserted_entities) > 0, "Expected entities to be upserted"
