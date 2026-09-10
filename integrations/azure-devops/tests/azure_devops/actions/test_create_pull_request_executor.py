from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from azure_devops.actions.create_pull_request_executor import (
    CreatePullRequestExecutor,
    CreatePullRequestInputs,
    _parse_create_pull_request_inputs,
)
from azure_devops.actions.exceptions import (
    CreatePullRequestError,
    InvalidActionParametersError,
)
from azure_devops.client.azure_devops_client import CreatePullRequestOptions
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def _make_run(props: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="create_pull_request"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="create_pull_request",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock._organization_base_url = "https://dev.azure.com/my-org"
    mock.create_pull_request = AsyncMock()
    return mock


@pytest.fixture
def executor(client: MagicMock) -> CreatePullRequestExecutor:
    instance = CreatePullRequestExecutor()
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
        "title": "Add feature",
        "sourceRefName": "feature/add-feature",
        "targetRefName": "main",
    }
    props.update(overrides)
    return props


def test_parse_create_pull_request_inputs_accepts_valid_strings() -> None:
    inputs = _parse_create_pull_request_inputs(
        {
            "organization": "my-org",
            "project": "proj-guid",
            "repositoryId": "repo-guid",
            "title": "Add feature",
            "sourceRefName": "feature/add-feature",
            "targetRefName": "main",
            "description": "Optional description",
        }
    )

    assert inputs == CreatePullRequestInputs(
        organization="my-org",
        project="proj-guid",
        repositoryId="repo-guid",
        title="Add feature",
        sourceRefName="feature/add-feature",
        targetRefName="main",
        description="Optional description",
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
            "title": "Add feature",
            "sourceRefName": "feature/add-feature",
            "targetRefName": "main",
        },
    ],
)
def test_parse_create_pull_request_inputs_rejects_missing_or_empty_values(
    properties: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        _parse_create_pull_request_inputs(properties)


def test_parse_create_pull_request_inputs_rejects_non_string_values() -> None:
    with pytest.raises(ValueError):
        _parse_create_pull_request_inputs(
            {
                "organization": "my-org",
                "project": "proj-guid",
                "repositoryId": "repo-guid",
                "title": 123,
                "sourceRefName": "feature/add-feature",
                "targetRefName": "main",
            }
        )


@pytest.mark.asyncio
async def test_execute_missing_repository_id_raises(
    executor: CreatePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(repositoryId="")))


@pytest.mark.asyncio
async def test_execute_missing_title_raises(
    executor: CreatePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(title="")))


@pytest.mark.asyncio
async def test_execute_rejects_non_string_title(
    executor: CreatePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run(_valid_props(title=123)))


@pytest.mark.asyncio
async def test_execute_organization_mismatch_raises(
    executor: CreatePullRequestExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run(_valid_props(organization="other-org")))

    assert "does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_creates_pull_request_and_completes_run(
    executor: CreatePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request.return_value = {
        "pullRequestId": 42,
        "_links": {
            "web": {
                "href": "https://dev.azure.com/my-org/My%20Project/_git/repo/pullrequest/42"
            }
        },
    }
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.create_pull_request_executor.ocean", mock_ocean
    )

    run = _make_run(_valid_props())
    await executor.execute(run)

    create_call = client.create_pull_request.await_args
    assert create_call is not None
    assert create_call.args[0] == "proj-guid"
    assert create_call.args[1] == "repo-guid"
    options = create_call.args[2]
    assert isinstance(options, CreatePullRequestOptions)
    assert options.title == "Add feature"
    assert options.source_ref_name == "feature/add-feature"
    assert options.target_ref_name == "main"

    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        success=True,
        message="Pull request #42 created: https://dev.azure.com/my-org/My%20Project/_git/repo/pullrequest/42",
    )


@pytest.mark.asyncio
async def test_execute_wraps_http_error_as_create_pull_request_error(
    executor: CreatePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://dev.azure.com"),
        response=httpx.Response(status_code=409, json={"message": "active PR exists"}),
    )
    monkeypatch.setattr(
        "azure_devops.actions.create_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(CreatePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "active PR exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_malformed_response_raises(
    executor: CreatePullRequestExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.create_pull_request.return_value = {}
    monkeypatch.setattr(
        "azure_devops.actions.create_pull_request_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(CreatePullRequestError) as exc_info:
        await executor.execute(_make_run(_valid_props()))

    assert "incomplete response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_partition_key_returns_none_when_inputs_missing(
    executor: CreatePullRequestExecutor,
) -> None:
    assert await executor._get_partition_key(_make_run({})) is None


@pytest.mark.asyncio
async def test_partition_key(
    executor: CreatePullRequestExecutor,
) -> None:
    assert (
        await executor._get_partition_key(_make_run(_valid_props()))
        == "my-org/proj-guid/repo-guid"
    )
