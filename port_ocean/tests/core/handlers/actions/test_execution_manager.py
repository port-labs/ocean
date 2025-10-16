import asyncio
from typing import Any
import uuid
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
import pytest
from port_ocean.clients.port.client import PortClient
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.actions.execution_manager import (
    ExecutionManager,
    ActionRunTask,
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
    IntegrationFeatureFlag,
    InvocationType,
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
    integrationActionExecutionProperties: dict[str, Any] = {},
) -> ActionRun[IntegrationActionInvocationPayload]:
    return ActionRun(
        id=f"test-run-id-{uuid.uuid4()}",
        action=MagicMock(name="bla"),
        payload=IntegrationActionInvocationPayload(
            type=InvocationType.INTEGRATION_ACTION,
            installationId="test-installation-id",
            actionType=action_type,
            integrationActionExecutionProperties=integrationActionExecutionProperties,
        ),
        status=RunStatus.IN_PROGRESS,
    )


def generate_mock_action_run_task(
    visibility_expiration_timestamp: datetime | None = None,
    queue_name: str | None = None,
) -> ActionRunTask:
    return ActionRunTask(
        visibility_expiration_timestamp=(
            visibility_expiration_timestamp
            if visibility_expiration_timestamp is not None
            else (datetime.now() + timedelta(minutes=5))
        ),
        queue_name=queue_name or GLOBAL_SOURCE,
        run=generate_mock_action_run(),
    )


@pytest.fixture
def mock_port_client() -> MagicMock:
    mock_port_client = MagicMock(spec=PortClient)
    mock_port_client.get_pending_runs = AsyncMock()
    mock_port_client.acknowledge_run = AsyncMock()
    mock_port_client.get_run_by_external_id = AsyncMock()
    mock_port_client.patch_run = AsyncMock()
    mock_port_client.post_run_log = AsyncMock()
    mock_port_client.get_organization_feature_flags = AsyncMock(
        return_value=[IntegrationFeatureFlag.OCEAN_EXECUTION_AGENT_ELIGIBLE]
    )
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
def mock_ocean_context(monkeypatch: pytest.MonkeyPatch, mock_ocean: Ocean) -> MagicMock:
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
        visibility_timeout_seconds=30,
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
        visibility_timeout_seconds=30,
        max_wait_seconds_before_shutdown=30,
    )
    execution_manager.register_executor(mock_test_executor)
    execution_manager.register_executor(mock_test_partition_executor)
    execution_manager._actions_executors = {
        mock_test_executor.ACTION_NAME: mock_test_executor,
        mock_test_partition_executor.ACTION_NAME: mock_test_partition_executor,
    }
    return execution_manager


class TestExecutionManager:
    @pytest.mark.asyncio
    async def test_register_executor(
        self,
        execution_manager_without_executors: ExecutionManager,
        mock_webhook_manager: MagicMock,
        mock_test_executor: MagicMock,
    ):
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
    ):
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
    ):
        # Arrange
        mock_test_action_run_task = generate_mock_action_run_task()

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(mock_test_action_run_task)
            mock_port_client.acknowledge_run.assert_called_once_with(
                mock_test_action_run_task.run.id
            )
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_run_should_not_execute_run_if_acknowledge_conflicts(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        mock_test_action_run_task = generate_mock_action_run_task()
        mock_port_client.acknowledge_run.side_effect = RunAlreadyAcknowledgedError()

        # Act
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(mock_test_action_run_task)

            # Assert
            mock_port_client.acknowledge_run.assert_called_once_with(
                mock_test_action_run_task.run.id
            )
            mock_execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_run_expired_visibility_and_not_deduplicated_should_try_to_process(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        mock_test_action_run_task = generate_mock_action_run_task()
        expired_task = mock_test_action_run_task.copy(
            update={
                "visibility_expiration_timestamp": datetime.now() - timedelta(minutes=1)
            }
        )

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(expired_task)
            mock_port_client.acknowledge_run.assert_called_once_with(
                expired_task.run.id
            )
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_run_expired_visibility_and_deduplicated_should_be_skipped(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        expired_task = generate_mock_action_run_task(
            visibility_expiration_timestamp=datetime.now() - timedelta(minutes=1)
        )
        execution_manager._deduplication_set.add(expired_task.run.id)

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._execute_run(expired_task)
            mock_port_client.acknowledge_run.assert_not_called()
            mock_execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_run_should_sleep_if_rate_limited(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
        mock_test_executor: MagicMock,
    ):
        # Arrange
        few_seconds_away = datetime.now() + timedelta(seconds=0.1)
        mock_test_executor.is_close_to_rate_limit = AsyncMock(
            side_effect=lambda: few_seconds_away > datetime.now()
        )
        mock_test_executor.get_remaining_seconds_until_rate_limit = AsyncMock(
            side_effect=lambda: (few_seconds_away - datetime.now()).total_seconds()
        )
        execution_manager._actions_executors[mock_test_executor.ACTION_NAME] = (
            mock_test_executor
        )
        mock_test_action_run_task = generate_mock_action_run_task()

        # Act
        await execution_manager._execute_run(mock_test_action_run_task)

        # Assert
        mock_port_client.post_run_log.assert_called_with(
            mock_test_action_run_task.run.id,
            ANY,
        )

    @pytest.mark.asyncio
    async def test_get_queues_size_with_global_and_partition_queues(
        self, execution_manager: ExecutionManager
    ):
        # Arrange
        await execution_manager._global_queue.put(generate_mock_action_run_task())
        await execution_manager._global_queue.put(generate_mock_action_run_task())

        execution_manager._partition_queues["partition1"] = (
            execution_manager._global_queue.__class__()
        )
        await execution_manager._partition_queues["partition1"].put(
            generate_mock_action_run_task()
        )

        # Act
        size = await execution_manager._get_queues_size()

        # Assert
        assert size == 3

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_add_source_to_active_when_empty(
        self, execution_manager: ExecutionManager
    ):
        # Arrange
        run = generate_mock_action_run()
        visibility_expiration = datetime.now() + timedelta(minutes=5)

        # Act
        await execution_manager._add_run_to_queue(
            run, GLOBAL_SOURCE, visibility_expiration
        )

        # Assert
        assert await execution_manager._global_queue.size() == 1
        active_source = await execution_manager._active_sources.get()
        assert active_source == GLOBAL_SOURCE
        assert run.id in execution_manager._deduplication_set

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_not_add_source_when_queue_has_items(
        self, execution_manager: ExecutionManager
    ):
        # Arrange
        run1 = generate_mock_action_run()
        run2 = generate_mock_action_run()
        visibility_expiration = datetime.now() + timedelta(minutes=5)

        # Act & Assert
        await execution_manager._add_run_to_queue(
            run1, GLOBAL_SOURCE, visibility_expiration
        )

        with patch.object(execution_manager._active_sources, "put") as mock_add_source:
            await execution_manager._add_run_to_queue(
                run2, GLOBAL_SOURCE, visibility_expiration
            )
            mock_add_source.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_run_to_queue_should_create_queue_if_not_exists(
        self, execution_manager: ExecutionManager
    ):
        # Arrange
        queue_name = "test_action:partition1"
        run_task = generate_mock_action_run_task(queue_name=queue_name)

        # Act
        await execution_manager._add_run_to_queue(
            run_task.run, queue_name, run_task.visibility_expiration_timestamp
        )

        # Assert
        assert queue_name in execution_manager._partition_queues
        assert queue_name in execution_manager._queues_locks
        assert await execution_manager._partition_queues[queue_name].size() == 1

    @pytest.mark.asyncio
    async def test_handle_global_queue_once_should_process_run_and_remove_dedup(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        run_task = generate_mock_action_run_task()
        await execution_manager._add_run_to_queue(
            run_task.run,
            GLOBAL_SOURCE,
            run_task.visibility_expiration_timestamp,
        )

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._handle_global_queue_once()

            assert run_task.run.id not in execution_manager._deduplication_set
            mock_port_client.acknowledge_run.assert_called_once_with(run_task.run.id)
            mock_execute.assert_called_once_with(run_task.run)

    @pytest.mark.asyncio
    async def test_handle_partition_queue_once_should_process_run(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        partition_name = "test_action:partition1"
        run_task = generate_mock_action_run_task(queue_name=partition_name)
        await execution_manager._add_run_to_queue(
            run_task.run,
            partition_name,
            run_task.visibility_expiration_timestamp,
        )

        # Act & Assert
        with patch.object(
            execution_manager._actions_executors["test_action"], "execute"
        ) as mock_execute:
            await execution_manager._handle_partition_queue_once(partition_name)

            assert run_task.run.id not in execution_manager._deduplication_set
            mock_port_client.acknowledge_run.assert_called_once_with(run_task.run.id)
            mock_execute.assert_called_once_with(run_task.run)

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_respect_high_watermark(
        self, execution_manager: ExecutionManager, mock_port_client: MagicMock
    ):
        # Arrange
        execution_manager._high_watermark = 2
        for _ in range(3):
            await execution_manager._global_queue.put(generate_mock_action_run_task())

        mock_port_client.get_pending_runs.return_value = []

        # Act
        polling_task = asyncio.create_task(execution_manager._poll_action_runs())
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        mock_port_client.get_pending_runs.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_poll_when_below_watermark(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0.1
        mock_run = generate_mock_action_run()
        mock_port_client.get_pending_runs.return_value = [mock_run]

        # Act
        polling_task = asyncio.create_task(execution_manager._poll_action_runs())
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        mock_port_client.get_pending_runs.assert_called()
        assert (
            await execution_manager._global_queue.size()
            == execution_manager._high_watermark
        )

    @pytest.mark.asyncio
    async def test_poll_action_runs_should_skip_unregistered_actions(
        self, execution_manager: ExecutionManager, mock_port_client: MagicMock
    ):
        # Arrange
        execution_manager._high_watermark = 10
        execution_manager._poll_check_interval_seconds = 0.1
        mock_run = generate_mock_action_run()
        mock_run.payload.actionType = "unregistered_action"
        mock_port_client.get_pending_runs.return_value = [mock_run]

        # Act
        polling_task = asyncio.create_task(execution_manager._poll_action_runs())
        await asyncio.sleep(0.1)
        await execution_manager._gracefully_cancel_task(polling_task)

        # Assert
        assert await execution_manager._get_queues_size() == 0

    @pytest.mark.asyncio
    async def test_shutdown_should_cancel_polling_and_waits_for_workers(
        self,
        execution_manager: ExecutionManager,
    ):
        # Arrange
        execution_manager._max_wait_seconds_before_shutdown = 1.0
        await execution_manager.start_processing_action_runs()

        # Act
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
    ):
        # Arrange
        execution_manager._max_wait_seconds_before_shutdown = 1
        execution_manager._high_watermark = 50
        execution_manager._poll_check_interval_seconds = 0.1
        mock_port_client.get_pending_runs.return_value = [
            generate_mock_action_run() for _ in range(10)
        ]
        await execution_manager.start_processing_action_runs()

        # Act
        ack_calls_count = mock_port_client.acknowledge_run.call_count
        await execution_manager.shutdown()

        # Assert
        assert mock_port_client.acknowledge_run.call_count == ack_calls_count

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Not been tested yet")
    async def test_concurrent_workers_no_deadlock(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
    ):
        """Test that multiple workers can process runs concurrently without deadlocking"""
        # Arrange
        num_runs = 10
        for i in range(num_runs):
            run_task = generate_mock_action_run_task()
            await execution_manager._global_queue.put(run_task)
            if i == 0:
                await execution_manager._active_sources.put(GLOBAL_SOURCE)

        # Create multiple workers
        workers = []
        for _ in range(3):
            worker = asyncio.create_task(
                self._process_n_items(execution_manager, num_runs // 3)
            )
            workers.append(worker)

        # Act
        try:
            await asyncio.wait_for(asyncio.gather(*workers), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Workers deadlocked")

        # Assert - all runs should be processed
        assert await execution_manager._global_queue.size() == 0

    async def _process_n_items(self, manager: ExecutionManager, n: int):
        """Helper to process N items from queues"""
        for _ in range(n):
            try:
                source = await asyncio.wait_for(
                    manager._active_sources.get(), timeout=1.0
                )
                if source == GLOBAL_SOURCE:
                    await manager._handle_global_queue_once()
            except asyncio.TimeoutError:
                break

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Not been tested yet")
    async def test_global_and_partition_queues_isolation(
        self,
        execution_manager: ExecutionManager,
        mock_test_partition_executor: MagicMock,
        mock_port_client: MagicMock,
    ):
        """Test that partition queues process sequentially while global queue processes concurrently"""

        # Arrange
        class RunMeasurement(BaseModel):
            start_time: datetime
            end_time: datetime

        partition1 = f"{mock_test_partition_executor.ACTION_NAME}:partition1"
        partition2 = f"{mock_test_partition_executor.ACTION_NAME}:partition2"
        run_measurements: dict[str, list[RunMeasurement]] = {
            partition1: [],
            partition2: [],
            GLOBAL_SOURCE: [],
        }

        execution_manager._workers_count = 5
        execution_manager._high_watermark = 20
        execution_manager._poll_check_interval_seconds = 0.1
        execution_manager._max_wait_seconds_before_shutdown = 1

        # Patch the relevant methods to record execution timings for measurement
        original_handle_global_queue_once = execution_manager._handle_global_queue_once
        original_handle_partition_queue_once = (
            execution_manager._handle_partition_queue_once
        )

        async def wrapped_handle_global_queue_once():
            run_task = None
            # Peek the run_task to get the run and its queue; need to lock to do so.
            async with execution_manager._queues_locks[GLOBAL_SOURCE]:
                if await execution_manager._global_queue.size() > 0:
                    run_task = await execution_manager._global_queue.peek()
            run_id = run_task.run.id if run_task else None
            measurement = RunMeasurement(start_time=datetime.now(), end_time=None)
            if run_id:
                run_measurements[GLOBAL_SOURCE].append(measurement)
            await original_handle_global_queue_once()
            if run_id:
                measurement.end_time = datetime.now()

        async def wrapped_handle_partition_queue_once(partition_name: str):
            queue = execution_manager._partition_queues[partition_name]
            run_task = None
            # Peek the run_task to get the run at the head of the queue, if present
            async with execution_manager._queues_locks[partition_name]:
                if await queue.size() > 0:
                    run_task = await queue.peek()
            run_id = run_task.run.id if run_task else None
            measurement = RunMeasurement(start_time=datetime.now(), end_time=None)
            if run_id:
                run_measurements[partition_name].append(measurement)
            await original_handle_partition_queue_once(partition_name)
            if run_id:
                measurement.end_time = datetime.now()

        execution_manager._handle_global_queue_once = wrapped_handle_global_queue_once
        execution_manager._handle_partition_queue_once = (
            wrapped_handle_partition_queue_once
        )
        mock_port_client.get_pending_runs.return_value = [
            *[
                generate_mock_action_run(
                    action_type=mock_test_partition_executor.ACTION_NAME,
                    integrationActionExecutionProperties={"partition_name": partition1},
                )
                for _ in range(5)
            ],
            *[
                generate_mock_action_run(
                    action_type=mock_test_partition_executor.ACTION_NAME,
                    integrationActionExecutionProperties={"partition_name": partition2},
                )
                for _ in range(5)
            ],
            *[generate_mock_action_run() for _ in range(5)],
        ]

        def check_queue_measurements(queue_name: str):
            queue_measurements = run_measurements[queue_name]
            for idx, measurement in enumerate(queue_measurements):
                if idx == len(queue_measurements) - 1:
                    continue
                if queue_name == GLOBAL_SOURCE:
                    assert measurement.end_time < queue_measurements[idx + 1].start_time
                else:
                    assert (
                        measurement.end_time >= queue_measurements[idx + 1].start_time
                    )

        # Act
        await execution_manager.start_processing_action_runs()
        # Allow sufficient time for some action runs to be processed
        await asyncio.sleep(3)
        await execution_manager.shutdown()

        # Assert
        assert execution_manager._polling_task.cancelled()
        assert len(execution_manager._workers_pool) == 0
        assert len(run_measurements[GLOBAL_SOURCE]) > 0
        assert len(run_measurements[partition1]) > 0
        assert len(run_measurements[partition2]) > 0
        for queue_name in run_measurements:
            check_queue_measurements(queue_name)

    @pytest.mark.asyncio
    async def test_execute_run_handles_general_exception(
        self,
        execution_manager: ExecutionManager,
        mock_port_client: MagicMock,
        mock_test_executor: MagicMock,
    ):
        # Arrange
        run_task = generate_mock_action_run_task()
        error_msg = "Test error"
        mock_test_executor.execute.side_effect = Exception(error_msg)

        # Act
        await execution_manager._execute_run(run_task)

        # Assert
        mock_port_client.patch_run.assert_called_once_with(
            run_task.run.id, {"summary": error_msg, "status": RunStatus.FAILURE}
        )
