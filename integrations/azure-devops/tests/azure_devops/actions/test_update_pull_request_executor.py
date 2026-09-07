from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    UpdatePullRequestError,
)
from azure_devops.actions.update_pull_request_executor import UpdatePullRequestExecutor
from azure_devops.client.azure_devops_client import UpdatePullRequestOptions

PULL_REQUEST_URL = "https://dev.azure.com/org/proj/_git/repo/pullrequest/42"


def _make_run(props: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="update_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_pull_request",
            integrationActionExecutionProperties=props,
        ),
    )


def _updated_pull_request(status: str = "active") -> dict[str, Any]:
    return {
        "pullRequestId": 42,
        "status": status,
        "_links": {"web": {"href": PULL_REQUEST_URL}},
    }


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.get_single_project = AsyncMock(return_value={"id": "proj-guid"})
    mock.get_repository_by_name = AsyncMock(return_value={"id": "repo-guid"})
    mock.get_pull_request = AsyncMock()
    mock.update_pull_request = AsyncMock(return_value=_updated_pull_request())
    return mock


@pytest.fixture
def executor(client: MagicMock) -> UpdatePullRequestExecutor:
    instance = UpdatePullRequestExecutor()
    instance._client = client
    return instance


def _make_mock_ocean() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    return mock_ocean


@pytest.fixture
def mock_ocean(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = _make_mock_ocean()
    monkeypatch.setattr("azure_devops.actions.update_pull_request_executor.ocean", mock)
    return mock


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "props",
    [
        {"repository": "repo", "pullRequestId": "42", "title": "New"},
        {"project": "proj", "pullRequestId": "42", "title": "New"},
        {"project": "proj", "repository": "repo", "title": "New"},
    ],
    ids=["missing_project", "missing_repository", "missing_pull_request_id"],
)
async def test_execute_missing_required_parameters_raises(
    executor: UpdatePullRequestExecutor, props: dict[str, Any]
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(props))


@pytest.mark.asyncio
async def test_execute_without_any_updated_field_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run({"project": "proj", "repository": "repo", "pullRequestId": "42"})
        )

    assert "At least one field to update is required" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_invalid_status_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "status": "merged",
                }
            )
        )

    assert "Invalid status 'merged'" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_updates_pull_request_and_reports_completion(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    run = _make_run(
        {
            "project": "My Project",
            "repository": "repo",
            "pullRequestId": "42",
            "title": "Updated title",
            "description": "Updated description",
            "targetBranch": "main",
        }
    )
    await executor.execute(run)

    client.get_single_project.assert_awaited_once_with("My Project")
    # The update route is keyed by repository ID, so a supplied name is resolved.
    client.get_repository_by_name.assert_awaited_once_with("proj-guid", "repo")
    update_call = client.update_pull_request.await_args
    assert update_call is not None
    assert update_call.args[0] == "proj-guid"
    assert update_call.args[1] == "repo-guid"
    assert update_call.args[2] == "42"
    options = update_call.args[3]
    assert isinstance(options, UpdatePullRequestOptions)
    assert options.title == "Updated title"
    assert options.description == "Updated description"
    assert options.target_branch == "main"
    assert options.last_merge_source_commit is None

    # A status of "completed" is what requires the extra lookup, so a plain
    # metadata update must not pay for it.
    client.get_pull_request.assert_not_awaited()

    completed_call = mock_ocean.port_client.report_run_completed.await_args
    assert completed_call is not None
    assert completed_call.args[0] is run
    assert completed_call.kwargs["success"] is True
    assert PULL_REQUEST_URL in completed_call.kwargs["message"]


@pytest.mark.asyncio
async def test_execute_completing_pull_request_sends_last_merge_source_commit(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.get_pull_request.return_value = {
        "pullRequestId": 42,
        "lastMergeSourceCommit": {
            "commitId": "abc123",
            "url": "https://dev.azure.com/org/_apis/git/commits/abc123",
        },
    }
    client.update_pull_request.return_value = _updated_pull_request("completed")

    await executor.execute(
        _make_run(
            {
                "project": "proj",
                "repository": "repo",
                "pullRequestId": "42",
                "status": "Completed",
                "mergeStrategy": "SQUASH",
                "deleteSourceBranch": True,
            }
        )
    )

    client.get_pull_request.assert_awaited_once_with("42")
    options = client.update_pull_request.await_args.args[3]
    # Inputs are matched against the API's casing rather than passed through.
    assert options.status == "completed"
    assert options.merge_strategy == "squash"
    assert options.delete_source_branch is True
    # Narrowed to the commit ID rather than forwarding the whole GitCommitRef.
    assert options.last_merge_source_commit == {"commitId": "abc123"}
    assert mock_ocean.port_client.report_run_completed.await_count == 1


@pytest.mark.asyncio
async def test_execute_completing_without_merge_commit_raises(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.get_pull_request.return_value = {"pullRequestId": 42}

    with pytest.raises(UpdatePullRequestError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "status": "completed",
                }
            )
        )

    assert "cannot be completed" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_project_not_found_raises(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.get_single_project.return_value = None

    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "missing",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "title": "New",
                }
            )
        )

    assert "was not found" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_repository_not_found_raises(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.get_repository_by_name.return_value = None

    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "missing-repo",
                    "pullRequestId": "42",
                    "title": "New",
                }
            )
        )

    assert "Repository 'missing-repo' was not found" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_description_over_limit_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "description": "x" * 4001,
                }
            )
        )

    assert "at most 4000 characters" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_wraps_http_error_as_update_pull_request_error(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.update_pull_request.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("PATCH", "https://dev.azure.com"),
        response=httpx.Response(
            status_code=400, json={"message": "pull request is not active"}
        ),
    )

    with pytest.raises(UpdatePullRequestError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "status": "abandoned",
                }
            )
        )

    assert "pull request is not active" in str(exc_info.value)
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_malformed_response_raises(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.update_pull_request.return_value = {}

    with pytest.raises(UpdatePullRequestError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj",
                    "repository": "repo",
                    "pullRequestId": "42",
                    "title": "New",
                }
            )
        )

    assert "unexpected response" in str(exc_info.value)
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_partition_key_serializes_runs_per_pull_request(
    executor: UpdatePullRequestExecutor,
) -> None:
    run = _make_run({"project": "proj", "repository": "repo", "pullRequestId": "42"})
    assert await executor._get_partition_key(run) == "proj/repo/42"


@pytest.mark.asyncio
async def test_partition_key_missing_inputs_returns_none(
    executor: UpdatePullRequestExecutor,
) -> None:
    assert await executor._get_partition_key(_make_run({})) is None
