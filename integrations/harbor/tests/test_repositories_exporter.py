from typing import Any, AsyncIterator
from urllib.parse import unquote

import pytest

from integrations.harbor.exporters.repositories import RepositoriesExporter


class _StubHarborClient:
    def __init__(self, pages_by_project: dict[str, list[list[dict[str, Any]]]]) -> None:
        self.pages_by_project = pages_by_project

    async def iter_pages(
        self, path: str, **_: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        project = path.split("/projects/")[-1].split("/")[0]
        project = unquote(project)
        for page in self.pages_by_project.get(project, []):
            yield page


@pytest.mark.asyncio
async def test_repositories_exporter_maps_repositories() -> None:
    client = _StubHarborClient(
        pages_by_project={
            "alpha": [
                [
                    {
                        "name": "alpha/library/nginx",
                        "artifact_count": 4,
                        "pull_count": 20,
                        "creation_time": "2024-01-01T00:00:00Z",
                        "update_time": "2024-01-02T00:00:00Z",
                        "id": 101,
                    }
                ]
            ]
        }
    )

    exporter = RepositoriesExporter(
        client,
        project_records=[{"project_name": "alpha", "project_id": 1}],
    )

    repos: list[dict[str, Any]] = []
    async for batch in exporter.iter_repositories():
        repos.extend(batch)

    assert repos == [
        {
            "repository_id": 101,
            "project_id": 1,
            "project_name": "alpha",
            "repository_name": "library/nginx",
            "repository_path": "alpha/library/nginx",
            "artifact_count": 4,
            "pull_count": 20,
            "creation_time": "2024-01-01T00:00:00Z",
            "update_time": "2024-01-02T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_repositories_exporter_applies_filters() -> None:
    client = _StubHarborClient(
        pages_by_project={
            "alpha": [[{"name": "alpha/service-api", "artifact_count": 1}]],
            "beta": [[{"name": "beta/library-web", "artifact_count": 2}]],
        }
    )

    exporter = RepositoriesExporter(
        client,
        project_records=[
            {"project_name": "alpha", "project_id": 1},
            {"project_name": "beta", "project_id": 2},
        ],
        project_filter=["beta"],
        name_prefix="library",
        name_contains="web",
    )

    repos: list[dict[str, Any]] = []
    async for batch in exporter.iter_repositories():
        repos.extend(batch)

    assert len(repos) == 1
    assert repos[0]["project_name"] == "beta"
    assert repos[0]["repository_name"] == "library-web"
