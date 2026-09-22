from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    UpdatePullRequestLabelsError,
)
from azure_devops.actions.update_pull_request_labels_executor import (
    UpdatePullRequestLabelsExecutor,
    UpdatePullRequestLabelsInputs,
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
        action=ActionRun.Action(identifier="update_pull_request_labels"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_pull_request_labels",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock._organization_base_url = "https://dev.azure.com/my-org"
    mock.create_pull_request_label = AsyncMock()
    return mock


@pytest.fixture
def executor(client: MagicMock) -> UpdatePullRequestLabelsExecutor:
    instance = UpdatePullRequestLabelsExecutor()
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
        "label": "approved",
    }
    props.update(overrides)
    return props


def test_inputs_from_execution_properties_accepts_valid_strings() -> None:
    inputs = UpdatePullRequestLabelsInputs.from_execution_properties(_valid_props())

    assert inputs == UpdatePullRequestLabelsInputs(
        organization="my-org",
        project="proj-guid",
        repositoryId="repo-guid",
        pullRequestId="42",
        label="approved",
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
            "pullRequestId": "42",
        },
        {
            "organization": "my-org",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
            "label": "",
        },
    ],
)
def test_inputs_from_execution_properties_rejects_missing_or_empty_values(
    properties: dict[str, str],
) -> None:
    with pytest.raises(InvalidActionParametersError):
        UpdatePullRequestLabelsInputs.from_execution_properties(properties)


def test_inputs_from_execution_properties_rejects_non_string_values() -> None:
    with pytest.raises(InvalidActionParametersError):
        UpdatePullRequestLabelsInputs.from_execution_properties(
            _valid_props(pullRequestId=42)
        )


@pytest.mark.asyncio
async def test_execute_organization_mismatch_raises(
    executor: UpdatePullRequestLabelsExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(organization="other-org")))

    assert "does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_adds_label_and_completes_run(
    executor: UpdatePullRequestLabelsExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request_label.return_value = {
        "id": "label-guid",
        "name": "approved",
        "active": True,
    }
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.update_pull_request_labels_executor.ocean", mock_ocean
    )

    run = _make_run(_valid_props())
    await executor.execute(run)

    client.create_pull_request_label.assert_awaited_once_with(
        "proj-guid", "repo-guid", "42", "approved"
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        success=True,
        message="Label 'approved' added to pull request 42",
    )


@pytest.mark.asyncio
async def test_execute_wraps_http_error(
    executor: UpdatePullRequestLabelsExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request_label.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://dev.azure.com"),
        response=httpx.Response(
            status_code=404, json={"message": "pull request not found"}
        ),
    )
    monkeypatch.setattr(
        "azure_devops.actions.update_pull_request_labels_executor.ocean",
        _make_mock_ocean(),
    )

    with pytest.raises(UpdatePullRequestLabelsError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "pull request not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_rejects_incomplete_response(
    executor: UpdatePullRequestLabelsExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request_label.return_value = {}
    monkeypatch.setattr(
        "azure_devops.actions.update_pull_request_labels_executor.ocean",
        _make_mock_ocean(),
    )

    with pytest.raises(UpdatePullRequestLabelsError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "incomplete" in str(exc_info.value)


@pytest.mark.asyncio
async def test_partition_key(executor: UpdatePullRequestLabelsExecutor) -> None:
    run = _make_run(_valid_props())

    assert await executor._get_partition_key(run) == "my-org/proj-guid/repo-guid/42"
