from typing import Any, AsyncGenerator
from datetime import datetime, timedelta
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
    options: SingleWorkflowOptions = {
        "organization": "test-org",
        "repo_name": "test",
        "workflow_id": "12343",
    }

    # Create an async mock to return the test repos
    async def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return TEST_DATA["workflows"][0]

    with patch.object(
        rest_client, "send_api_request", side_effect=mock_request
    ) as mock_request:
        async with event_context("test_event"):
            wf = await exporter.get_resource(options)
            assert wf == {**TEST_DATA["workflows"][0], "__organization": "test-org"}
            mock_request.assert_called_with(
                f"{rest_client.base_url}/repos/test-org/{options['repo_name']}/actions/workflows/{options['workflow_id']}"
            )


@pytest.mark.asyncio
async def test_get_paginated_resources(rest_client: GithubRestClient) -> None:
    options: ListWorkflowOptions = {"organization": "test-org", "repo_name": "test"}
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
            assert wf[0] == [
                {**workflow, "__organization": "test-org"}
                for workflow in TEST_DATA["workflows"]
            ]

        mock_request.assert_called_once_with(
            f"{rest_client.base_url}/repos/test-org/{options['repo_name']}/actions/workflows"
        )


@pytest.mark.asyncio
async def test_has_workflow_changes_since_with_commits(
    rest_client: GithubRestClient,
) -> None:
    """Test has_workflow_changes_since returns True when commits are found."""
    exporter = RestWorkflowExporter(rest_client)
    cursor = datetime.utcnow() - timedelta(days=1)

    commits_response = [{"sha": "abc123", "commit": {"message": "workflow change"}}]

    async def mock_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield commits_response

    with patch.object(
        rest_client, "send_paginated_request", side_effect=mock_paginated_request
    ):
        async with event_context("test_event"):
            has_changes = await exporter.has_workflow_changes_since(
                "test-org", "test-repo", cursor
            )

            assert has_changes is True


@pytest.mark.asyncio
async def test_has_workflow_changes_since_no_cursor(
    rest_client: GithubRestClient,
) -> None:
    """Test has_workflow_changes_since returns True when cursor is None."""
    exporter = RestWorkflowExporter(rest_client)

    async with event_context("test_event"):
        has_changes = await exporter.has_workflow_changes_since(
            "test-org", "test-repo", None
        )

        assert has_changes is True


@pytest.mark.asyncio
async def test_has_workflow_changes_since_no_commits(
    rest_client: GithubRestClient,
) -> None:
    """Test has_workflow_changes_since returns False when no commits found."""
    exporter = RestWorkflowExporter(rest_client)
    cursor = datetime.utcnow() - timedelta(days=1)

    async def mock_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield []  # No commits

    with patch.object(
        rest_client, "send_paginated_request", side_effect=mock_paginated_request
    ):
        async with event_context("test_event"):
            has_changes = await exporter.has_workflow_changes_since(
                "test-org", "test-repo", cursor
            )

            assert has_changes is False


@pytest.mark.asyncio
async def test_has_workflow_changes_since_api_error(
    rest_client: GithubRestClient,
) -> None:
    """Test has_workflow_changes_since raises exception on API error."""
    exporter = RestWorkflowExporter(rest_client)
    cursor = datetime.utcnow() - timedelta(days=1)

    async def mock_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        raise Exception("API error")
        yield  # Never reached, but needed for async generator

    with patch.object(
        rest_client, "send_paginated_request", side_effect=mock_paginated_request
    ):
        async with event_context("test_event"):
            with pytest.raises(Exception, match="API error"):
                await exporter.has_workflow_changes_since(
                    "test-org", "test-repo", cursor
                )


@pytest.mark.asyncio
async def test_multi_repo_incremental_filtering(
    rest_client: GithubRestClient,
) -> None:
    """Test incremental filtering with multiple repos: some with changes, some without."""
    exporter = RestWorkflowExporter(rest_client)
    cursor = datetime.utcnow() - timedelta(days=1)

    # Simulate checking commits for 3 repos
    call_count = 0

    async def mock_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # repo-a: has changes
            yield [{"sha": "abc123"}]
        elif call_count == 2:
            # repo-b: no changes
            yield []
        elif call_count == 3:
            # repo-c: has changes
            yield [{"sha": "def456"}]

    repos_to_check = [
        {"name": "repo-a"},
        {"name": "repo-b"},
        {"name": "repo-c"},
    ]

    repos_with_changes = []

    with patch.object(
        rest_client, "send_paginated_request", side_effect=mock_paginated_request
    ):
        async with event_context("test_event"):
            for repo in repos_to_check:
                has_changes = await exporter.has_workflow_changes_since(
                    "test-org", repo["name"], cursor
                )
                if has_changes:
                    repos_with_changes.append(repo["name"])

    # Verify: only repos with changes are included
    assert repos_with_changes == ["repo-a", "repo-c"]
    assert "repo-b" not in repos_with_changes
    assert call_count == 3  # Called once per repo
