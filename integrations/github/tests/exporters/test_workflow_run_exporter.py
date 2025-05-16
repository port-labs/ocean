from typing import Any, AsyncGenerator
from httpx import Response
import pytest
from unittest.mock import MagicMock, patch
from github.core.exporters.workflow_runs_exporter import WorkflowRunExporter
from github.core.options import (
    ListWorkflowOptions,
    SingleWorkflowOptions,
)
from github.clients.base_client import AbstractGithubClient
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
            "event": "push",
            "display_title": "Update README.md",
            "status": "queued",
            "conclusion": None,
            "workflow_id": 159038,
            "url": "https://api.github.com/repos/octo-org/octo-repo/actions/runs/30433642",
            "html_url": "https://github.com/octo-org/octo-repo/actions/runs/30433642",
            "created_at": "2020-01-22T19:33:08Z",
            "updated_at": "2020-01-22T19:33:08Z",
            "run_started_at": "2020-01-22T19:33:08Z",
            "workflow_url": "https://api.github.com/repos/octo-org/octo-repo/actions/workflows/159038",
            "repository": {
                "id": 1296269,
                "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
                "events_url": "https://api.github.com/repos/octocat/Hello-World/events",
                "forks_url": "https://api.github.com/repos/octocat/Hello-World/forks",
            },
        }
    ],
}


@pytest.mark.asyncio
async def test_single_resource(client: AbstractGithubClient) -> None:
    exporter = WorkflowRunExporter(client)
    options: SingleWorkflowOptions = {"repo": "test", "resource_id": "12343"}

    # Create an async mock to return the test repos
    async def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        response = MagicMock(Response)
        response.json.return_value = TEST_DATA["workflow_runs"][0]
        return response

    with patch.object(
        client, "send_api_request", side_effect=mock_request
    ) as mock_request:
        async with event_context("test_event"):
            wf = await exporter.get_resource(options)
            assert wf == TEST_DATA["workflow_runs"][0]
            mock_request.assert_called_with(
                f"repos/{client.organization}/{options['repo']}/actions/runs/{options['resource_id']}"
            )


@pytest.mark.asyncio
async def test_get_paginated_resources(client: AbstractGithubClient) -> None:
    options: ListWorkflowOptions = {"repo": "test"}
    exporter = WorkflowRunExporter(client)

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
                batch async for batch in exporter.get_paginated_resources(options)
            ]

            assert len(wf) == 1
            assert len(wf[0]) == 1
            assert wf[0] == TEST_DATA["workflow_runs"]

        mock_request.assert_called_once_with(
            f"repos/{client.organization}/{options['repo']}/actions/runs"
        )
