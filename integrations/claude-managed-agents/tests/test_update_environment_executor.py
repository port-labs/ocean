from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from actions.exceptions import InvalidActionParametersException
from actions.update_environment_executor import (
    ENVIRONMENT_UPDATED_STATUS_LABEL,
    UpdateEnvironmentExecutor,
)
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


from tests.action_test_helpers import (
    build_executor,
    build_mock_ocean,
    mock_event_context,
    sdk_environment,
    update_env_run,
)


@pytest.mark.asyncio
async def test_update_environment_executor_updates_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.update_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(UpdateEnvironmentExecutor, client_mock)

    run = update_env_run()
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.update_environment.assert_awaited_once_with(
        "env_1", payload={"name": "new-name"}
    )
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        True,
        "Updated environment env_1",
        status_label=ENVIRONMENT_UPDATED_STATUS_LABEL,
    )


@pytest.mark.asyncio
async def test_update_environment_executor_sets_environment_id_output_for_workflow_nodes() -> (
    None
):
    client_mock = MagicMock()
    client_mock.update_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(UpdateEnvironmentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"environmentId": "env_1", "name": "n"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    assert run.output == {"environmentId": "env_1"}


@pytest.mark.asyncio
async def test_update_environment_executor_skips_output_for_classic_action_runs() -> (
    None
):
    """Classic self-service action runs have no structured output field, so the
    executor must not touch `.output` on them (it doesn't exist on `ActionRun`)."""
    client_mock = MagicMock()
    client_mock.update_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(UpdateEnvironmentExecutor, client_mock)

    run = MagicMock(spec=ActionRun)
    run.id = "run_1"
    run.execution_properties = {"environmentId": "env_1", "name": "n"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_environment_executor_requires_at_least_one_update_field() -> None:
    executor = build_executor(UpdateEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"environmentId": "env_1"}
    with pytest.raises(InvalidActionParametersException, match="at least one"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_update_environment_executor_requires_environment_id() -> None:
    executor = build_executor(UpdateEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"name": "n"}
    with pytest.raises(InvalidActionParametersException):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_update_environment_executor_raises_on_api_error() -> None:
    client_mock = MagicMock()
    client_mock.update_environment = AsyncMock(side_effect=RuntimeError("not found"))
    executor = build_executor(UpdateEnvironmentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="not found"):
            await executor.execute(update_env_run())

    mock_ocean.register_raw.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_environment_partition_key_is_environment_id() -> None:
    executor = build_executor(UpdateEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"environmentId": "env_1"}
    assert await executor._get_partition_key(run) == "env_1"
