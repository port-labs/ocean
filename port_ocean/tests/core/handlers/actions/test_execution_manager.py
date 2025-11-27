import asyncio
from typing import Any
import uuid
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from fastapi import APIRouter, FastAPI
from loguru import logger
from pydantic import BaseModel
import pytest
import httpx
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.client import PortClient
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.actions.execution_manager import (
    ExecutionManager,
    GLOBAL_SOURCE,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from port_ocean.exceptions.execution_manager import (
    DuplicateActionExecutorError,
    RunAlreadyAcknowledgedError,
)
from port_ocean.ocean import Ocean
from port_ocean.utils.signal import SignalHandler


def generate_mock_action_run(
    action_type: str = "test_action",
    integrationActionExecutionProperties: dict[str, Any] | None = None,
) -> ActionRun:
    if integrationActionExecutionProperties is None:
        integrationActionExecutionProperties = {}
    return ActionRun(
        id=f"test-run-id-{uuid.uuid4()}",
        status=RunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationActionType=action_type,
            integrationActionExecutionProperties=integrationActionExecutionProperties,
        ),
    )


@pytest.fixture
def mock_port_client() -> MagicMock:
    mock_port_client = MagicMock(spec=PortClient)
    mock_port_client.claim_pending_runs = AsyncMock()
    mock_port_client.acknowledge_run = AsyncMock()
    mock_port_client.get_run_by_external_id = AsyncMock()
    mock_port_client.patch_run = AsyncMock()
    mock_port_client.post_run_log = AsyncMock()
    mock_port_client.auth = AsyncMock(spec=PortAuthentication)
    mock_port_client.auth.is_machine_user = AsyncMock(return_value=True)
    return mock_port_client


@pytest.fixture
def mock_ocean(mock_port_client: PortClient) -> Ocean:
    ocean_mock = MagicMock(spec=Ocean)
    ocean_mock.config = MagicMock()
    ocean_mock.port_client = mock_port_client
    ocean_mock.integration_router = APIRouter()
    ocean_mock.fast_api_app = FastAPI()
    return ocean_mock


@pytest.fixture(autouse=True)
def mock_ocean_context(
    monkeypatch: pytest.MonkeyPatch, mock_ocean: Ocean
) -> PortOceanContext:
    mock_ocean_context = PortOceanContext(mock_ocean)
    mock_ocean_context._app = mock_ocean
    monkeypatch.setattr(
        "port_ocean.core.handlers.actions.execution_manager.ocean", mock_ocean_context
    )
    return mock_ocean_context


@pytest.fixture
def mock_webhook_manager() -> MagicMock:
    return MagicMock(spec=LiveEventsProcessorManager)


@pytest.fixture
def mock_signal_handler() -> MagicMock:
    return MagicMock(spec=SignalHandler)


@pytest.fixture
def mock_test_executor() -> MagicMock:
    mock_executor = MagicMock(spec=AbstractExecutor)
    mock_executor.ACTION_NAME = "test_action"
    mock_executor.WEBHOOK_PROCESSOR_CLASS = None
    mock_executor.WEBHOOK_PATH = None
    mock_executor._get_partition_key = AsyncMock(return_value=None)
    mock_executor.execute = AsyncMock(return_value=None)
    mock_executor.is_close_to_rate_limit = AsyncMock(return_value=False)
    mock_executor.get_remaining_seconds_until_rate_limit = AsyncMock(return_value=0.0)
    return mock_executor


@pytest.fixture
def mock_test_partition_executor() -> MagicMock:
    mock_executor = MagicMock(spec=AbstractExecutor)
    mock_executor.ACTION_NAME = "test_partition_action"
    mock_executor.WEBHOOK_PROCESSOR_CLASS = None
    mock_executor.WEBHOOK_PATH = None
    mock_executor._get_partition_key = AsyncMock(
        side_effect=lambda run: run.payload.integrationActionExecutionProperties.get(
            "partition_name", "default_partition"
        )
    )
    mock_executor.execute = AsyncMock(return_value=None)
    mock_executor.is_close_to_rate_limit = AsyncMock(return_value=False)
    mock_executor.get_remaining_seconds_until_rate_limit = AsyncMock(return_value=0.0)
    return mock_executor


@pytest.fixture
def execution_manager_without_executors(
    mock_webhook_manager: MagicMock, mock_signal_handler: MagicMock
) -> ExecutionManager:
    return ExecutionManager(
        webhook_manager=mock_webhook_manager,
        signal_handler=mock_signal_handler,
        workers_count=3,
        runs_buffer_high_watermark=100,
        poll_check_interval_seconds=5,
        visibility_timeout_ms=30,
        max_wait_seconds_before_shutdown=30,
    )


@pytest.fixture
def execution_manager(
    mock_webhook_manager: MagicMock,
    mock_signal_handler: MagicMock,
    mock_test_executor: MagicMock,
    mock_test_partition_executor: MagicMock,
) -> ExecutionManager:
    execution_manager = ExecutionManager(
        webhook_manager=mock_webhook_manager,
        signal_handler=mock_signal_handler,
        workers_count=3,
        runs_buffer_high_watermark=100,
        poll_check_interval_seconds=5,
        visibility_timeout_ms=30,
        max_wait_seconds_before_shutdown=30,
    )
    execution_manager.register_executor(mock_test_executor)
    execution_manager.register_executor(mock_test_partition_executor)
    return execution_manager


class TestExecutionManager:
    @pytest.mark.asyncio
    async def test_register_executor(
        self,
        execution_manager_without_executors: ExecutionManager,
        mock_webhook_manager: MagicMock,
        mock_test_executor: MagicMock,
    ) -> None:
        # Arrange
        mock_test_executor.WEBHOOK_PROCESSOR_CLASS = MagicMock(
            spec=AbstractWebhookProcessor
        )
        mock_test_executor.WEBHOOK_PATH = "/test-webhook"

        # Act
        execution_manager_without_executors.register_executor(mock_test_executor)

        # Assert
        assert (
            mock_test_executor.ACTION_NAME
            in execution_manager_without_executors._actions_executors
        )
        mock_webhook_manager.register_processor.assert_called_once_with(
            mock_test_executor.WEBHOOK_PATH,
            mock_test_executor.WEBHOOK_PROCESSOR_CLASS,
        )

    @pytest.mark.asyncio
    async def test_register_executor_should_raise_error_if_duplicate(
        self, execution_manager: ExecutionManager, mock_test_executor: MagicMock
    ) -> None:
        # Act & Assert
        with pytest.raises(
            DuplicateActionExecutorError,
            match="Executor for action 'test_action' is already registered",
        ):
            execution_manager.register_executor(mock_test_executor)

    @pytest.mark.asyncio
    async def test_execute_run_should_acknowledge_run_successfully(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        mock_test_action_run = generate_mock_action_run()

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(mock_test_action_run)
            mock_port_client.acknowledge_run.assert_called_once_with(
                mock_test_action_run.id
            )
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_run_should_not_execute_run_if_acknowledge_conflicts(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        mock_test_action_run = generate_mock_action_run()
        mock_port_client.acknowledge_run.side_effect = RunAlreadyAcknowledgedError()

        # Act
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(mock_test_action_run)

            # Assert
            mock_port_client.acknowledge_run.assert_called_once_with(
                mock_test_action_run.id
            )
            mock_execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_run_should_sleep_if_rate_limited(
        self,
        execution_manager_without_executors: ExecutionManager,
        mock_port_client: MagicMock,
        mock_test_executor: MagicMock,
    ) -> None:
        # Arrange
        few_seconds_away = datetime.now() + timedelta(seconds=0.1)
        mock_test_executor.is_close_to_rate_limit = AsyncMock(
            side_effect=lambda: few_seconds_away > datetime.now()
        )
        mock_test_executor.get_remaining_seconds_until_rate_limit = AsyncMock(
            side_effect=lambda: (few_seconds_away - datetime.now()).total_seconds()
        )
        execution_manager_without_executors.register_executor(mock_test_executor)
        mock_test_action_run = generate_mock_action_run()

        # Act
        await execution_manager_without_executors._execute_run(mock_test_action_run)

        # Assert
        mock_port_client.post_run_log.assert_called_with(
            mock_test_action_run.id,
            ANY,
        )

    @pytest.mark.asyncio
    async def test_get_queues_size_with_global_and_partition_queues(
        self, execution_manager: ExecutionManager
    ) -> None:
        # Arrange
        await execution_manager._global_queue.put(generate_mock_action_run())
        await execution_manager._global_queue.put(generate_mock_action_run())

        execution_manager._partition_queues["partition1"] = (
            execution_manager._global_queue.__class__()
        )
        await execution_manager._partition_queues["partition1"].put(
            generate_mock_action_run()
        )

        # Act
        size = await execution_manager._get_queues_size()

        # Assert
        assert size == 3

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_add_source_to_active_when_empty(
        self, execution_manager: ExecutionManager
    ) -> None:
        # Arrange
        run = generate_mock_action_run()

        # Act
        await execution_manager._add_run_to_queue(run, GLOBAL_SOURCE)

        # Assert
        assert await execution_manager._global_queue.size() == 1
        active_source = await execution_manager._active_sources.get()
        assert active_source == GLOBAL_SOURCE
        assert run.id in execution_manager._deduplication_set

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_not_add_source_when_queue_has_items(
        self, execution_manager: ExecutionManager
    ) -> None:
        # Arrange
        run1 = generate_mock_action_run()
        run2 = generate_mock_action_run()

        # Act & Assert
        await execution_manager._add_run_to_queue(run1, GLOBAL_SOURCE)

        with patch.object(execution_manager._active_sources, "put") as mock_add_source:
            await execution_manager._add_run_to_queue(run2, GLOBAL_SOURCE)
            mock_add_source.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_create_queue_if_not_exists(
        self, execution_manager: ExecutionManager
    ) -> None:
        # Arrange
        queue_name = "test_action:partition1"
        run = generate_mock_action_run()

        # Act
        await execution_manager._add_run_to_queue(run, queue_name)

        # Assert
        assert queue_name in execution_manager._partition_queues
        assert queue_name in execution_manager._queues_locks
        assert await execution_manager._partition_queues[queue_name].size() == 1

    @pytest.mark.asyncio
    async def test_handle_global_queue_once_should_process_run_and_remove_dedup(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        run = generate_mock_action_run()
        await execution_manager._add_run_to_queue(
            run,
            GLOBAL_SOURCE,
        )

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._handle_global_queue_once()

            assert run.id not in execution_manager._deduplication_set
            mock_port_client.acknowledge_run.assert_called_once_with(run.id)
            mock_execute.assert_called_once_with(run)

    @pytest.mark.asyncio
    async def test_handle_partition_queue_once_should_process_run(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        partition_name = "test_action:partition1"
        run = generate_mock_action_run()
        await execution_manager._add_run_to_queue(
            run,
            partition_name,
        )

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._handle_partition_queue_once(partition_name)

            assert run.id not in execution_manager._deduplication_set
            mock_port_client.acknowledge_run.assert_called_once_with(run.id)
            mock_execute.assert_called_once_with(run)

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_respect_high_watermark(
        self, execution_manager: ExecutionManager, mock_port_client: MagicMock
    ) -> None:
        # Arrange
        execution_manager._high_watermark = 2
        for _ in range(3):
            await execution_manager._global_queue.put(generate_mock_action_run())

        mock_port_client.claim_pending_runs.return_value = []

        # Act
        polling_task: asyncio.Task[None] = asyncio.create_task(
            execution_manager._poll_action_runs()
        )
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        mock_port_client.claim_pending_runs.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_poll_when_below_watermark(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0
        mock_port_client.claim_pending_runs.side_effect = (
            lambda limit, visibility_timeout_ms: [generate_mock_action_run()]
        )

        # Act
        polling_task: asyncio.Task[None] = asyncio.create_task(
            execution_manager._poll_action_runs()
        )
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        mock_port_client.claim_pending_runs.assert_called()
        assert (
            await execution_manager._global_queue.size()
            == execution_manager._high_watermark
        )

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_skip_unregistered_actions(
        self, execution_manager: ExecutionManager, mock_port_client: MagicMock
    ) -> None:
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0
        mock_port_client.claim_pending_runs.side_effect = (
            lambda limit, visibility_timeout_ms: [
                generate_mock_action_run(action_type="unregistered_action")
            ]
        )

        # Act
        polling_task: asyncio.Task[None] = asyncio.create_task(
            execution_manager._poll_action_runs()
        )
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        assert await execution_manager._get_queues_size() == 0

    @pytest.mark.asyncio
    async def test_shutdown_should_cancel_polling_and_waits_for_workers(
        self,
        execution_manager: ExecutionManager,
    ) -> None:
        # Arrange
        execution_manager._max_wait_seconds_before_shutdown = 1.0
        await execution_manager.start_processing_action_runs()

        # Act
        assert execution_manager._polling_task is not None
        assert (
            not execution_manager._polling_task.done()
            or execution_manager._polling_task.cancelled()
        )
        assert not execution_manager._is_shutting_down.is_set()
        assert len(execution_manager._workers_pool) == 3
        await execution_manager.shutdown()

        # Assert
        assert execution_manager._is_shutting_down.is_set()
        assert execution_manager._polling_task.cancelled()
        assert len(execution_manager._workers_pool) == 0

    @pytest.mark.asyncio
    async def test_shutdown_should_not_acknowledge_runs_after_shutdown_started(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        execution_manager._max_wait_seconds_before_shutdown = 1.0
        execution_manager._high_watermark = 50
        execution_manager._poll_check_interval_seconds = 0
        mock_port_client.claim_pending_runs.return_value = [
            generate_mock_action_run() for _ in range(10)
        ]
        await execution_manager.start_processing_action_runs()

        # Act
        ack_calls_count: int = mock_port_client.acknowledge_run.call_count
        await execution_manager.shutdown()

        # Assert
        assert mock_port_client.acknowledge_run.call_count == ack_calls_count

    @pytest.mark.asyncio
    async def test_global_and_partition_queues_concurrency(
        self,
        execution_manager_without_executors: ExecutionManager,
        mock_test_executor: MagicMock,
        mock_test_partition_executor: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        """Test that partition queues process sequentially while global queue processes concurrently"""

        # Arrange
        class RunMeasurement(BaseModel):
            start_time: datetime
            end_time: datetime

        partition1 = "partition1"
        partition2 = "partition2"
        partition1_queue_name = f"{mock_test_partition_executor.ACTION_NAME}:partition1"
        partition2_queue_name = f"{mock_test_partition_executor.ACTION_NAME}:partition2"
        run_measurements: dict[str, list[RunMeasurement]] = {
            partition1_queue_name: [],
            partition2_queue_name: [],
            GLOBAL_SOURCE: [],
        }

        execution_manager_without_executors._workers_count = 5
        execution_manager_without_executors._high_watermark = 20
        execution_manager_without_executors._poll_check_interval_seconds = 0
        execution_manager_without_executors._max_wait_seconds_before_shutdown = 1.0

        async def mock_execute(
            run: ActionRun,
        ) -> None:
            await asyncio.sleep(0.1)
            return None

        mock_test_executor.execute.side_effect = mock_execute
        mock_test_partition_executor.execute.side_effect = mock_execute
        execution_manager_without_executors.register_executor(mock_test_executor)
        execution_manager_without_executors.register_executor(
            mock_test_partition_executor
        )

        # Patch the relevant methods to record execution timings for measurement
        original_handle_global_queue_once = (
            execution_manager_without_executors._handle_global_queue_once
        )
        original_handle_partition_queue_once = (
            execution_manager_without_executors._handle_partition_queue_once
        )

        async def wrapped_handle_global_queue_once() -> None:
            start_time = datetime.now()
            await original_handle_global_queue_once()
            try:
                run_measurements[GLOBAL_SOURCE].append(
                    RunMeasurement(start_time=start_time, end_time=datetime.now())
                )
            except Exception as e:
                logger.error(f"Error recording run measurement: {e}")

        async def wrapped_handle_partition_queue_once(partition_name: str) -> None:
            start_time = datetime.now()
            await original_handle_partition_queue_once(partition_name)
            try:
                run_measurements[partition_name].append(
                    RunMeasurement(start_time=start_time, end_time=datetime.now())
                )
            except Exception as e:
                logger.error(f"Error recording run measurement: {e}")

        setattr(
            execution_manager_without_executors,
            "_handle_global_queue_once",
            wrapped_handle_global_queue_once,
        )
        setattr(
            execution_manager_without_executors,
            "_handle_partition_queue_once",
            wrapped_handle_partition_queue_once,
        )
        mock_port_client.claim_pending_runs.side_effect = (
            lambda limit, visibility_timeout_ms: [
                *[
                    generate_mock_action_run(
                        action_type=mock_test_partition_executor.ACTION_NAME,
                        integrationActionExecutionProperties={
                            "partition_name": partition1
                        },
                    )
                    for _ in range(5)
                ],
                *[
                    generate_mock_action_run(
                        action_type=mock_test_partition_executor.ACTION_NAME,
                        integrationActionExecutionProperties={
                            "partition_name": partition2
                        },
                    )
                    for _ in range(5)
                ],
                *[generate_mock_action_run() for _ in range(5)],
            ]
        )

        def check_global_queue_measurements() -> None:
            queue_measurements = run_measurements[GLOBAL_SOURCE]
            assert any(
                m.end_time >= queue_measurements[i + 1].start_time
                for i, m in enumerate(queue_measurements[:-1])
            )

        def check_partition_queue_measurements(queue_name: str) -> None:
            queue_measurements = run_measurements[queue_name]
            for idx, measurement in enumerate(queue_measurements):
                if idx == len(queue_measurements) - 1:
                    continue
                assert measurement.end_time < queue_measurements[idx + 1].start_time

        # Act
        await execution_manager_without_executors.start_processing_action_runs()
        await asyncio.sleep(1)
        await execution_manager_without_executors.shutdown()

        # Assert
        assert execution_manager_without_executors._polling_task is not None
        assert execution_manager_without_executors._polling_task.cancelled()
        assert len(execution_manager_without_executors._workers_pool) == 0
        for queue_name in run_measurements:
            assert len(run_measurements[queue_name]) > 0
            if queue_name == GLOBAL_SOURCE:
                check_global_queue_measurements()
            else:
                check_partition_queue_measurements(queue_name)

    @pytest.mark.asyncio
    async def test_execute_run_handles_general_exception(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
        mock_test_executor: MagicMock,
    ) -> None:
        # Arrange
        run = generate_mock_action_run()
        error_msg = "Test error"
        mock_test_executor.execute.side_effect = Exception(error_msg)

        # Act
        await execution_manager._execute_run(run)

        # Assert
        assert mock_port_client.patch_run.call_count == 1
        called_args, _ = mock_port_client.patch_run.call_args
        assert called_args[0] == run.id
        patch_data = called_args[1]
        assert error_msg in patch_data["summary"]
        assert patch_data["status"] == RunStatus.FAILURE

    @pytest.mark.asyncio
    async def test_execute_run_handles_acknowledge_run_api_error(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        run = generate_mock_action_run()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        mock_port_client.acknowledge_run.side_effect = http_error

        # Act
        await execution_manager._execute_run(run)

        # Assert
        assert mock_port_client.patch_run.call_count == 1
        called_args, _ = mock_port_client.patch_run.call_args
        assert called_args[0] == run.id
        patch_data = called_args[1]
        patch_data["summary"] == "Failed to trigger run execution"
        assert patch_data["status"] == RunStatus.FAILURE

    @pytest.mark.asyncio
    async def test_polling_continues_after_api_errors(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        """Verify that polling loop continues running even after multiple API errors"""
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0

        poll_count = 0

        async def claim_runs_with_errors(
            limit: int, visibility_timeout_ms: int
        ) -> list[ActionRun]:
            nonlocal poll_count
            poll_count += 1
            # Fail on first and third attempts, succeed on second and fourth
            if poll_count in [1, 3]:
                mock_response = MagicMock(spec=httpx.Response)
                mock_response.status_code = 500
                raise httpx.HTTPStatusError(
                    "500 Internal Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            return [generate_mock_action_run()]

        mock_port_client.claim_pending_runs.side_effect = claim_runs_with_errors

        # Act
        polling_task: asyncio.Task[None] = asyncio.create_task(
            execution_manager._poll_action_runs()
        )
        await asyncio.sleep(0.2)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        # Polling should have continued through errors
        assert poll_count >= 4
        assert mock_port_client.claim_pending_runs.call_count >= 4
        # Should have successfully processed runs from successful polls
        assert await execution_manager._get_queues_size() > 0

    @pytest.mark.asyncio
    async def test_process_actions_runs_handles_exceptions_gracefully(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
        mock_test_executor: MagicMock,
    ) -> None:
        """Verify that _process_actions_runs catches exceptions and doesn't crash the worker"""
        # Arrange
        run = generate_mock_action_run()

        # Make execute raise an exception, and patch_run also fail
        mock_test_executor.execute.side_effect = Exception("Execution failed")
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        patch_error = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        mock_port_client.patch_run.side_effect = patch_error

        # Add run to queue
        await execution_manager._add_run_to_queue(run, GLOBAL_SOURCE)

        # Act
        # Start worker loop which should handle exceptions gracefully
        worker_task = asyncio.create_task(execution_manager._process_actions_runs())

        # Wait for worker to process the run
        await asyncio.sleep(0.1)

        # Signal shutdown - worker should still be running (not crashed)
        execution_manager._is_shutting_down.set()

        # Wait a bit more to ensure worker handles shutdown
        await asyncio.sleep(0.1)

        # Cancel worker
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Assert
        # Exception should have been caught by worker loop, not crashed
        # Run should have been acknowledged before execution failed
        mock_port_client.acknowledge_run.assert_called_once_with(run.id)
        # patch_run should have been attempted (even if it failed)
        mock_port_client.patch_run.assert_called_once()
        # Worker task should have completed (either naturally or cancelled), not crashed
        assert worker_task.done()

    @pytest.mark.asyncio
    async def test_poll_action_runs_continues_after_error_handling_runs(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ) -> None:
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0

        # First call succeeds, second call fails, third call succeeds again
        call_count = 0

        async def claim_runs_side_effect(
            limit: int, visibility_timeout_ms: int
        ) -> list[ActionRun]:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                mock_response = MagicMock(spec=httpx.Response)
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                raise httpx.HTTPStatusError(
                    "500 Internal Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            return [generate_mock_action_run()]

        mock_port_client.claim_pending_runs.side_effect = claim_runs_side_effect

        # Act
        polling_task: asyncio.Task[None] = asyncio.create_task(
            execution_manager._poll_action_runs()
        )
        await asyncio.sleep(0.15)  # Allow multiple poll attempts
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        # Should have attempted to poll multiple times, handling the error gracefully
        assert mock_port_client.claim_pending_runs.call_count >= 2
        # Should have successfully added runs from successful polls
        assert await execution_manager._get_queues_size() > 0
