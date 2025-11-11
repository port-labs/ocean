from typing import Any

import pytest

from integrations.harbor.exporters.projects import ProjectsExporter


class StubHarborClient:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages

    async def iter_pages(self, *args: Any, **kwargs: Any) -> Any:
        for page in self._pages:
            yield page


@pytest.mark.asyncio
async def test_projects_exporter_maps_and_streams() -> None:
    client = StubHarborClient(
        pages=[
            [
                {
                    "name": "alpha",
                    "repo_count": 3,
                    "owner_name": "team-a",
                    "metadata": {"public": "true", "display_name": "Alpha"},
                    "project_id": 1,
                },
                {
                    "name": "beta",
                    "repo_count": 1,
                    "owner_name": "team-b",
                    "metadata": {"public": "false"},
                    "project_id": 2,
                },
            ]
        ]
    )

    exporter = ProjectsExporter(client)

    batches: list[list[dict[str, Any]]] = []
    async for batch in exporter.iter_projects():
        batches.append(batch)

    assert batches == [
        [
            {
                "project_name": "alpha",
                "display_name": "Alpha",
                "public": True,
                "repository_count": 3,
                "owner": "team-a",
                "visibility": "public",
                "project_id": 1,
            },
            {
                "project_name": "beta",
                "display_name": "beta",
                "public": False,
                "repository_count": 1,
                "owner": "team-b",
                "visibility": "private",
                "project_id": 2,
            },
        ]
    ]


@pytest.mark.asyncio
async def test_projects_exporter_applies_filters() -> None:
    client = StubHarborClient(
        pages=[
            [
                {"name": "alpha", "metadata": {"public": "true"}},
                {"name": "beta", "metadata": {"public": "false"}},
                {"name": "alpha-service", "metadata": {"public": "true"}},
            ]
        ]
    )

    exporter = ProjectsExporter(
        client,
        include_names=["alpha", "alpha-service"],
        visibility_filter=["public"],
        name_prefix="alpha",
    )

    batches: list[list[dict[str, Any]]] = []
    async for batch in exporter.iter_projects():
        batches.append(batch)

    assert len(batches) == 1
    assert [item["project_name"] for item in batches[0]] == [
        "alpha",
        "alpha-service",
    ]
