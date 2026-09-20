from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    MergePullRequestError,
)
from azure_devops.actions.merge_pull_request_executor import (
    MergePullRequestExecutor,
    MergePullRequestInputs,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def _make_run(props: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="merge_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="merge_pull_request",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock._organization_base_url = "https://dev.azure.com/my-org"
    mock.merge_pull_request = AsyncMock()
    return mock


@pytest.fixture
def executor(client: MagicMock) -> MergePullRequestExecutor:
    instance = MergePullRequestExecutor()
    instance._client = client
    return instance


def _make_mock_ocean() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    return mock_ocean


def _valid_props(**overrides: Any) -> dict[str, Any]:
    props = {
        "organization": "my-org",
        "project": "proj-guid",
        "repositoryId": "repo-guid",
        "pullRequestId": "42",
    }
    props.update(overrides)
    return props


def test_merge_pull_request_inputs_from_execution_properties_accepts_valid_strings() -> (
    None
):
    inputs = MergePullRequestInputs.from_execution_properties(
        {
            "organization": "my-org",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
        }
    )

    assert inputs == MergePullRequestInputs(
        organization="my-org",
        project="proj-guid",
        repositoryId="repo-guid",
        pullRequestId="42",
    )


@pytest.mark.parametrize(
    "properties",
    [
        {},
        {"organization": "my-org"},
        {
            "organization": "my-org",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
        },
        {
            "organization": "",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
        },
    ],
)
def test_merge_pull_request_inputs_from_execution_properties_rejects_missing_or_empty_values(
    properties: dict[str, str],
) -> None:
    with pytest.raises(InvalidActionParametersError):
        MergePullRequestInputs.from_execution_properties(properties)


def test_merge_pull_request_inputs_from_execution_properties_rejects_non_string_values() -> (
    None
):
    with pytest.raises(InvalidActionParametersError):
        MergePullRequestInputs.from_execution_properties(
            {
                "organization": "my-org",
                "project": "proj-guid",
                "repositoryId": "repo-guid",
                "pullRequestId": 42,
            }
        )


@pytest.mark.asyncio
async def test_execute_missing_pull_request_id_raises(
    executor: MergePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(pullRequestId="")))


@pytest.mark.asyncio
async def test_execute_rejects_non_string_pull_request_id(
    executor: MergePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(pullRequestId=42)))


@pytest.mark.asyncio
async def test_execute_organization_mismatch_raises(
    executor: MergePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(organization="other-org")))

    assert "does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_merges_pull_request_and_completes_run(
    executor: MergePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.merge_pull_request.return_value = {
        "pullRequestId": 42,
        "status": "completed",
    }
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.merge_pull_request_executor.ocean", mock_ocean
    )

    run = _make_run(_valid_props())
    await executor.execute(run)

    client.merge_pull_request.assert_awaited_once_with("proj-guid", "repo-guid", "42")
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        success=True,
        message="Pull request #42 merged",
    )


@pytest.mark.asyncio
async def test_execute_wraps_http_error_as_merge_pull_request_error(
    executor: MergePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.merge_pull_request.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("PATCH", "https://dev.azure.com"),
        response=httpx.Response(
            status_code=404, json={"message": "pull request not found"}
        ),
    )
    monkeypatch.setattr(
        "azure_devops.actions.merge_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(MergePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "pull request not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_malformed_response_raises(
    executor: MergePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.merge_pull_request.return_value = {}
    monkeypatch.setattr(
        "azure_devops.actions.merge_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(MergePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "incomplete response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_wraps_runtime_error_as_merge_pull_request_error(
    executor: MergePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.merge_pull_request.side_effect = RuntimeError(
        "Pull request is not ready to merge: lastMergeSourceCommit is missing. "
        "Wait for Azure DevOps to finish computing the merge preview and retry."
    )
    monkeypatch.setattr(
        "azure_devops.actions.merge_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(MergePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "lastMergeSourceCommit is missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_partition_key_returns_none_when_inputs_missing(
    executor: MergePullRequestExecutor,
) -> None:
    assert await executor._get_partition_key(_make_run({})) is None


@pytest.mark.asyncio
async def test_partition_key(
    executor: MergePullRequestExecutor,
) -> None:
    assert (
        await executor._get_partition_key(_make_run(_valid_props()))
        == "my-org/proj-guid/repo-guid/42"
    )
