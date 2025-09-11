from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.core.options import (
    ListWorkflowRunOptions,
    SingleWorkflowRunOptions,
)
from port_ocean.context.event import event_context


TEST_DATA: dict[str, Any] = {
    "total_count": 1,
    "workflow_runs": [
        {
            "id": 30433642,
            "name": "Build",
            "node_id": "MDEyOldvcmtmbG93IFJ1bjI2OTI4OQ==",
            "path": ".github/workflows/build.yml@main",
            "run_number": 562,
            "display_title": "Update README.md",
            "status": "queued",
            "workflow_id": 159038,
            "url": "https://api.github.com/repos/octo-org/octo-repo/actions/runs/30433642",
            "repository": {
                "id": 1296269,
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
            },
        }
    ],
}


@pytest.mark.asyncio
async def test_single_resource(rest_client: GithubRestClient) -> None:
    exporter = RestWorkflowRunExporter(rest_client)
    options: SingleWorkflowRunOptions = {"repo_name": "test", "run_id": "12343"}

    # Create an async mock to return the test repos
    async def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return TEST_DATA["workflow_runs"][0]

    with patch.object(
        rest_client, "send_api_request", side_effect=mock_request
    ) as mock_request:
        async with event_context("test_event"):
            wf = await exporter.get_resource(options)
            assert wf == TEST_DATA["workflow_runs"][0]
            mock_request.assert_called_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/{options['repo_name']}/actions/runs/{options['run_id']}"
            )


@pytest.mark.asyncio
async def test_get_paginated_resources(rest_client: GithubRestClient) -> None:
    options: ListWorkflowRunOptions = {
        "repo_name": "test",
        "max_runs": 100,
        "workflow_id": 159038,
    }
    exporter = RestWorkflowRunExporter(rest_client)

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
            assert len(wf[0]) == 1
            assert wf[0] == TEST_DATA["workflow_runs"]

        mock_request.assert_called_once_with(
            f"{rest_client.base_url}/repos/{rest_client.organization}/{options['repo_name']}/actions/workflows/159038/runs"
        )
