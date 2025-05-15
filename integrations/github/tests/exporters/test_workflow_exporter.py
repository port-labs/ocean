from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, MagicMock
import httpx
from github.core.exporters.workflows_exporter import WorkflowExporter
from github.clients.base_client import AbstractGithubClient
from integration import GithubRepositorySelector
from github.utils import RepositoryType
from port_ocean.context.event import event_context


TEST_DATA: dict[str, Any] = {
    "total_count": 2,
    "workflows": [
        {
            "id": 161335,
            "name": "CI",
            "path": ".github/workflows/blank.yaml",
            "state": "active",
            "created_at": "2020-01-08T23:48:37.000-08:00",
            "url": "https://HOSTNAME/repos/octo-org/octo-repo/actions/workflows/161335",
        },
        {
            "id": 269289,
            "name": "Linter",
            "path": ".github/workflows/linter.yaml",
            "state": "active",
            "created_at": "2020-01-08T23:48:37.000-08:00",
            "url": "https://HOSTNAME/repos/octo-org/octo-repo/actions/workflows/269289",
        },
    ],
}


@pytest.mark.asyncio
class TestRepositoryExporter:
    async def test_get_paginated_resources(self, client: AbstractGithubClient) -> None:
        selector = GithubRepositorySelector(query="true")
        exporter = WorkflowExporter(client)

        # Create an async mock to return the test repos
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            yield TEST_DATA

        with patch.object(
            client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                wf: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(selector)
                ]

                assert len(wf) == 1
                assert len(wf[0]) == 2
                assert wf[0] == TEST_DATA["workflows"]

            mock_request.assert_called_once_with(
                f"orgs/{client.organization}/repos", {"type": RepositoryType.ALL}
            )
