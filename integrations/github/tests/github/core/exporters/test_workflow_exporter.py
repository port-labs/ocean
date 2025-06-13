from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.workflows_exporter import (
    RestWorkflowExporter,
)
from github.core.options import (
    ListWorkflowOptions,
    SingleWorkflowOptions,
)
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
            "__repository": "test",
        },
        {
            "id": 269289,
            "name": "Linter",
            "path": ".github/workflows/linter.yaml",
            "state": "active",
            "created_at": "2020-01-08T23:48:37.000-08:00",
            "url": "https://HOSTNAME/repos/octo-org/octo-repo/actions/workflows/269289",
            "__repository": "test",
        },
    ],
}


@pytest.mark.asyncio
async def test_single_resource(rest_client: GithubRestClient) -> None:
    exporter = RestWorkflowExporter(rest_client)
    options: SingleWorkflowOptions = {"repo_name": "test", "workflow_id": "12343"}

    # Create an async mock to return the test repos
    async def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return TEST_DATA["workflows"][0]

    with patch.object(
        rest_client, "send_api_request", side_effect=mock_request
    ) as mock_request:
        async with event_context("test_event"):
            wf = await exporter.get_resource(options)
            assert wf == TEST_DATA["workflows"][0]
            mock_request.assert_called_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/{options['repo_name']}/actions/workflows/{options['workflow_id']}"
            )


@pytest.mark.asyncio
async def test_get_paginated_resources(rest_client: GithubRestClient) -> None:
    options: ListWorkflowOptions = {"repo_name": "test"}
    exporter = RestWorkflowExporter(rest_client)

    # Create an async mock to return the test repos
    async def mock_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield TEST_DATA

    with patch.object(
        rest_client, "send_paginated_request", side_effect=mock_paginated_request
    ) as mock_request:
        async with event_context("test_event"):
            wf: list[list[dict[str, Any]]] = [
                batch async for batch in exporter.get_paginated_resources(options)
            ]

            assert len(wf) == 1
            assert len(wf[0]) == 2
            assert wf[0] == TEST_DATA["workflows"]

        mock_request.assert_called_once_with(
            f"{rest_client.base_url}/repos/{rest_client.organization}/{options['repo_name']}/actions/workflows"
        )
