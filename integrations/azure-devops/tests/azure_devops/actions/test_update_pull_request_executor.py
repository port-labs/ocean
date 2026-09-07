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
from azure_devops.actions.update_pull_request_executor import (
    UpdatePullRequestExecutor,
    UpdatePullRequestInputs,
    _build_update_pull_request_body,
    _parse_policy_config_ids,
    _parse_update_pull_request_inputs,
)

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
    mock.get_repository_pull_request = AsyncMock()
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


def _valid_props(**overrides: Any) -> dict[str, Any]:
    props = {
        "project": "proj-guid",
        "repositoryId": "repo-guid",
        "pullRequestId": "42",
        "title": "Updated title",
    }
    props.update(overrides)
    return props


def test_parse_update_pull_request_inputs_accepts_valid_strings() -> None:
    inputs = _parse_update_pull_request_inputs(
        {
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
            "title": "Updated title",
            "description": "Updated description",
            "status": "active",
            "targetBranch": "main",
            "mergeStrategy": "squash",
            "deleteSourceBranch": True,
            "mergeCommitMessage": "Merged via Port",
            "bypassPolicy": True,
            "bypassReason": "Emergency fix",
            "transitionWorkItems": True,
            "autoCompleteIgnoreConfigIds": "12, 34",
            "disableRenames": True,
            "conflictAuthorshipCommits": True,
            "detectRenameFalsePositives": False,
            "autoCompleteSetById": "user-guid",
        }
    )

    assert inputs == UpdatePullRequestInputs(
        project="proj-guid",
        repositoryId="repo-guid",
        pullRequestId="42",
        title="Updated title",
        description="Updated description",
        status="active",
        targetBranch="main",
        mergeStrategy="squash",
        deleteSourceBranch=True,
        mergeCommitMessage="Merged via Port",
        bypassPolicy=True,
        bypassReason="Emergency fix",
        transitionWorkItems=True,
        autoCompleteIgnoreConfigIds="12, 34",
        disableRenames=True,
        conflictAuthorshipCommits=True,
        detectRenameFalsePositives=False,
        autoCompleteSetById="user-guid",
    )


def test_build_update_pull_request_body_maps_all_optional_fields() -> None:
    inputs = UpdatePullRequestInputs(
        project="proj-guid",
        repositoryId="repo-guid",
        pullRequestId="42",
        bypassPolicy=True,
        bypassReason="Approved by release manager",
        transitionWorkItems=True,
        autoCompleteIgnoreConfigIds="12,34",
        disableRenames=True,
        conflictAuthorshipCommits=True,
        detectRenameFalsePositives=False,
        autoCompleteSetById="user-guid",
    )

    body = _build_update_pull_request_body(inputs, "completed", "squash")

    assert body == {
        "status": "completed",
        "autoCompleteSetBy": {"id": "user-guid"},
        "mergeOptions": {
            "disableRenames": True,
            "conflictAuthorshipCommits": True,
            "detectRenameFalsePositives": False,
        },
        "completionOptions": {
            "mergeStrategy": "squash",
            "bypassPolicy": True,
            "bypassReason": "Approved by release manager",
            "transitionWorkItems": True,
            "autoCompleteIgnoreConfigIds": [12, 34],
        },
    }


def test_parse_policy_config_ids_rejects_invalid_values() -> None:
    with pytest.raises(InvalidActionParametersError):
        _parse_policy_config_ids("12,abc")


@pytest.mark.parametrize(
    "properties",
    [
        {},
        {"project": "proj-guid"},
        {"project": "proj-guid", "repositoryId": "repo-guid"},
        {
            "project": "",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
            "title": "Updated title",
        },
    ],
)
def test_parse_update_pull_request_inputs_rejects_missing_or_empty_values(
    properties: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        _parse_update_pull_request_inputs(properties)


def test_parse_update_pull_request_inputs_rejects_non_string_values() -> None:
    with pytest.raises(ValueError):
        _parse_update_pull_request_inputs(
            {
                "project": "proj-guid",
                "repositoryId": "repo-guid",
                "pullRequestId": 42,
                "title": "Updated title",
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "props",
    [
        {"repositoryId": "repo-guid", "pullRequestId": "42", "title": "New"},
        {"project": "proj-guid", "pullRequestId": "42", "title": "New"},
        {"project": "proj-guid", "repositoryId": "repo-guid", "title": "New"},
    ],
    ids=["missing_project", "missing_repository_id", "missing_pull_request_id"],
)
async def test_execute_missing_required_parameters_raises(
    executor: UpdatePullRequestExecutor, props: dict[str, Any]
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(props))


@pytest.mark.asyncio
async def test_execute_rejects_non_string_pull_request_id(
    executor: UpdatePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(pullRequestId=42)))


@pytest.mark.asyncio
async def test_execute_without_any_updated_field_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(
            _make_run(
                {
                    "project": "proj-guid",
                    "repositoryId": "repo-guid",
                    "pullRequestId": "42",
                }
            )
        )

    assert "At least one field to update is required" in str(exc_info.value)
    assert "autoCompleteSetById" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_accepts_boolean_only_update_field(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    await executor.execute(
        _make_run(
            {
                "project": "proj-guid",
                "repositoryId": "repo-guid",
                "pullRequestId": "42",
                "transitionWorkItems": True,
            }
        )
    )

    body = client.update_pull_request.await_args.args[3]
    assert body == {"completionOptions": {"transitionWorkItems": True}}


@pytest.mark.asyncio
async def test_execute_invalid_status_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(status="merged")))

    assert "Invalid status 'merged'" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_updates_pull_request_and_reports_completion(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    run = _make_run(
        _valid_props(
            description="Updated description",
            targetBranch="main",
        )
    )
    await executor.execute(run)

    update_call = client.update_pull_request.await_args
    assert update_call is not None
    assert update_call.args[0] == "proj-guid"
    assert update_call.args[1] == "repo-guid"
    assert update_call.args[2] == "42"
    body = update_call.args[3]
    assert body == {
        "title": "Updated title",
        "description": "Updated description",
        "targetRefName": "refs/heads/main",
    }

    # A status of "completed" is what requires the extra lookup, so a plain
    # metadata update must not pay for it.
    client.get_repository_pull_request.assert_not_awaited()

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
    client.get_repository_pull_request.return_value = {
        "pullRequestId": 42,
        "lastMergeSourceCommit": {
            "commitId": "abc123",
            "url": "https://dev.azure.com/org/_apis/git/commits/abc123",
        },
    }
    client.update_pull_request.return_value = _updated_pull_request("completed")

    await executor.execute(
        _make_run(
            _valid_props(
                title=None,
                status="Completed",
                mergeStrategy="SQUASH",
                deleteSourceBranch=True,
            )
        )
    )

    client.get_repository_pull_request.assert_awaited_once_with(
        "proj-guid", "repo-guid", "42"
    )
    body = client.update_pull_request.await_args.args[3]
    assert body["status"] == "completed"
    assert body["completionOptions"] == {
        "mergeStrategy": "squash",
        "deleteSourceBranch": True,
    }
    assert body["lastMergeSourceCommit"] == {
        "commitId": "abc123",
        "url": "https://dev.azure.com/org/_apis/git/commits/abc123",
    }
    assert mock_ocean.port_client.report_run_completed.await_count == 1


@pytest.mark.asyncio
async def test_execute_completing_without_merge_commit_raises(
    executor: UpdatePullRequestExecutor,
    client: MagicMock,
    mock_ocean: MagicMock,
) -> None:
    client.get_repository_pull_request.return_value = {"pullRequestId": 42}

    with pytest.raises(UpdatePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props(title=None, status="completed")))

    assert "cannot be completed" in str(exc_info.value)
    client.update_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_description_over_limit_raises(
    executor: UpdatePullRequestExecutor, client: MagicMock
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(description="x" * 4001)))

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
        await executor.execute(_make_run(_valid_props(title=None, status="abandoned")))

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
        await executor.execute(_make_run(_valid_props()))

    assert "unexpected response" in str(exc_info.value)
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_partition_key_serializes_runs_per_pull_request(
    executor: UpdatePullRequestExecutor,
) -> None:
    run = _make_run(_valid_props(title=None))
    assert await executor._get_partition_key(run) == "proj-guid/repo-guid/42"


@pytest.mark.asyncio
async def test_partition_key_missing_inputs_returns_none(
    executor: UpdatePullRequestExecutor,
) -> None:
    assert await executor._get_partition_key(_make_run({})) is None
