from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from actions.delete_environment_executor import (
    ENVIRONMENT_DELETED_STATUS_LABEL,
    DeleteEnvironmentExecutor,
)
from actions.exceptions import InvalidActionParametersException
from port_ocean.exceptions.execution_manager import ActionExecutionError


from tests.action_test_helpers import (
    build_executor,
    build_mock_ocean,
    mock_event_context,
)


@pytest.mark.asyncio
async def test_delete_environment_executor_deletes_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.delete_environment = AsyncMock()
    executor = build_executor(DeleteEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"environmentId": "env_1"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.delete_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.delete_environment.assert_awaited_once_with("env_1")
    mock_ocean.unregister_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        True,
        "Deleted environment env_1",
        status_label=ENVIRONMENT_DELETED_STATUS_LABEL,
    )


@pytest.mark.asyncio
async def test_delete_environment_executor_reports_failure_on_api_error() -> None:
    client_mock = MagicMock()
    client_mock.delete_environment = AsyncMock(
        side_effect=RuntimeError("env not found")
    )
    executor = build_executor(DeleteEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"environmentId": "env_1"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.delete_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="env not found"):
            await executor.execute(run)

    mock_ocean.unregister_raw.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_environment_executor_posts_warn_log_when_catalog_deregister_fails() -> (
    None
):
    """Catalog deregistration is best-effort: a failure must not fail the run."""
    client_mock = MagicMock()
    client_mock.delete_environment = AsyncMock()
    executor = build_executor(DeleteEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"environmentId": "env_1"}

    mock_ocean = build_mock_ocean()
    mock_ocean.unregister_raw = AsyncMock(side_effect=RuntimeError("catalog down"))
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.delete_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    warn_calls = [
        call
        for call in mock_ocean.port_client.post_run_log.await_args_list
        if call.kwargs.get("level") == "WARNING"
    ]
    assert len(warn_calls) == 1
    assert warn_calls[0].args[0] is run
    assert "catalog down" in warn_calls[0].args[1]
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        True,
        "Deleted environment env_1",
        status_label=ENVIRONMENT_DELETED_STATUS_LABEL,
    )


@pytest.mark.asyncio
async def test_delete_environment_executor_requires_environment_id() -> None:
    executor = build_executor(DeleteEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {}
    with pytest.raises(InvalidActionParametersException):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_delete_environment_partition_key_is_environment_id() -> None:
    executor = build_executor(DeleteEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"environmentId": "env_1"}
    assert await executor._get_partition_key(run) == "env_1"
