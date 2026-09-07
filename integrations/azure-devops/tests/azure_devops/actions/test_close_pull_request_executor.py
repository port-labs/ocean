from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from azure_devops.actions.close_pull_request_executor import (
    ClosePullRequestExecutor,
    ClosePullRequestInputs,
    _parse_close_pull_request_inputs,
)
from azure_devops.actions.exceptions import (
    ClosePullRequestError,
    InvalidActionParametersError,
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
        action=ActionRun.Action(identifier="close_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="close_pull_request",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock._organization_base_url = "https://dev.azure.com/my-org"
    mock.close_pull_request = AsyncMock()
    return mock


@pytest.fixture
def executor(client: MagicMock) -> ClosePullRequestExecutor:
    instance = ClosePullRequestExecutor()
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


def test_parse_close_pull_request_inputs_accepts_valid_strings() -> None:
    inputs = _parse_close_pull_request_inputs(
        {
            "organization": "my-org",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "pullRequestId": "42",
        }
    )

    assert inputs == ClosePullRequestInputs(
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
def test_parse_close_pull_request_inputs_rejects_missing_or_empty_values(
    properties: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        _parse_close_pull_request_inputs(properties)


def test_parse_close_pull_request_inputs_rejects_non_string_values() -> None:
    with pytest.raises(ValueError):
        _parse_close_pull_request_inputs(
            {
                "organization": "my-org",
                "project": "proj-guid",
                "repositoryId": "repo-guid",
                "pullRequestId": 42,
            }
        )


@pytest.mark.asyncio
async def test_execute_missing_pull_request_id_raises(
    executor: ClosePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(pullRequestId="")))


@pytest.mark.asyncio
async def test_execute_rejects_non_string_pull_request_id(
    executor: ClosePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(pullRequestId=42)))


@pytest.mark.asyncio
async def test_execute_organization_mismatch_raises(
    executor: ClosePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(organization="other-org")))

    assert "does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_closes_pull_request_and_completes_run(
    executor: ClosePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.close_pull_request.return_value = {
        "pullRequestId": 42,
        "status": "abandoned",
        "_links": {
            "web": {
                "href": "https://dev.azure.com/my-org/My%20Project/_git/repo/pullrequest/42"
            }
        },
    }
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.close_pull_request_executor.ocean", mock_ocean
    )

    run = _make_run(_valid_props())
    await executor.execute(run)

    client.close_pull_request.assert_awaited_once_with("proj-guid", "repo-guid", "42")
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        success=True,
        message="Pull request #42 closed: https://dev.azure.com/my-org/My%20Project/_git/repo/pullrequest/42",
    )


@pytest.mark.asyncio
async def test_execute_wraps_http_error_as_close_pull_request_error(
    executor: ClosePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.close_pull_request.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("PATCH", "https://dev.azure.com"),
        response=httpx.Response(
            status_code=404, json={"message": "pull request not found"}
        ),
    )
    monkeypatch.setattr(
        "azure_devops.actions.close_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(ClosePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "pull request not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_malformed_response_raises(
    executor: ClosePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.close_pull_request.return_value = {}
    monkeypatch.setattr(
        "azure_devops.actions.close_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(ClosePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "incomplete response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_partition_key_returns_none_when_inputs_missing(
    executor: ClosePullRequestExecutor,
) -> None:
    assert await executor._get_partition_key(_make_run({})) is None


@pytest.mark.asyncio
async def test_partition_key(
    executor: ClosePullRequestExecutor,
) -> None:
    assert (
        await executor._get_partition_key(_make_run(_valid_props()))
        == "my-org/proj-guid/repo-guid/42"
    )
