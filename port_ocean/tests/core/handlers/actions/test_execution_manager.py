import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from port_ocean.clients.port.mixins.actions import RunAlreadyAcknowledgedError
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.actions.execution_manager import (
    ExecutionManager,
    ActionRunTask,
    GLOBAL_SOURCE,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.models import ActionRun, RunStatus
from port_ocean.utils.signal import SignalHandler


class MockWebhookProcessor(AbstractWebhookProcessor):
    async def handle_event(self, payload, resource_config):
        pass


class MockExecutor(AbstractExecutor):
    ACTION_NAME = "test_action"
    PARTITION_KEY = None
    WEBHOOK_PROCESSOR_CLASS = MockWebhookProcessor
    WEBHOOK_PATH = "/test-webhook"

    def __init__(self):
        self.execute_called = False
        self.rate_limit_reached = False
        self.rate_limit_wait_seconds = 0

    async def is_close_to_rate_limit(self) -> bool:
        return self.rate_limit_reached

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        return self.rate_limit_wait_seconds

    async def execute(self, payload):
        self.execute_called = True


class MockPartitionedExecutor(MockExecutor):
    ACTION_NAME = "test_partitioned_action"
    PARTITION_KEY = "partition_key"


@pytest.fixture
def mock_webhook_manager():
    return MagicMock(spec=LiveEventsProcessorManager)


@pytest.fixture
def mock_signal_handler():
    return MagicMock(spec=SignalHandler)


@pytest.fixture
def execution_manager(mock_webhook_manager, mock_signal_handler):
    return ExecutionManager(
        webhook_manager=mock_webhook_manager,
        signal_handler=mock_signal_handler,
        runs_buffer_high_watermark=100,
        poll_check_interval_seconds=1,
        sync_queue_lock_timeout_seconds=1.0,
    )


@pytest.fixture
def mock_action_run():
    return ActionRun(
        id="test-run-id",
        action=MagicMock(name="test_action"),
        payload={"oceanExecution": {}},
        status=RunStatus.PENDING,
    )


@pytest.fixture
def mock_action_run_task(mock_action_run):
    return ActionRunTask(
        visibility_expiration_timestamp=datetime.now() + timedelta(minutes=5),
        run=mock_action_run,
    )


class TestExecutionManager:
    @pytest.mark.asyncio
    async def test_register_executor(self, execution_manager, mock_webhook_manager):
        """Test registering an executor with webhook processor."""
        execution_manager.register_executor(MockExecutor)

        assert "test_action" in execution_manager._actions_executors
        mock_webhook_manager.register_processor.assert_called_once_with(
            "/test-webhook",
            MockWebhookProcessor,
            WebhookProcessorType.ACTION,
        )

    @pytest.mark.asyncio
    async def test_register_duplicate_executor(self, execution_manager):
        """Test registering duplicate executor raises ValueError."""
        execution_manager.register_executor(MockExecutor)

        with pytest.raises(
            ValueError, match="Executor for action 'test_action' is already registered"
        ):
            execution_manager.register_executor(MockExecutor)

    @pytest.mark.asyncio
    async def test_execute_run_success(self, execution_manager, mock_action_run_task):
        """Test successful execution of a run."""
        execution_manager.register_executor(MockExecutor)

        with patch.object(execution_manager, "acknowledge_run") as mock_acknowledge:
            await execution_manager._execute_run(mock_action_run_task)
            mock_acknowledge.assert_called_once_with(mock_action_run_task.run.id)

    @pytest.mark.asyncio
    async def test_execute_run_expired_visibility(
        self, execution_manager, mock_action_run
    ):
        """Test handling of expired visibility timeout."""
        expired_task = ActionRunTask(
            visibility_expiration_timestamp=datetime.now() - timedelta(minutes=5),
            run=mock_action_run,
        )
        execution_manager.register_executor(MockExecutor)

        with patch.object(execution_manager, "acknowledge_run") as mock_acknowledge:
            await execution_manager._execute_run(expired_task)
            mock_acknowledge.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_run_rate_limited(
        self, execution_manager, mock_action_run_task
    ):
        """Test handling of rate limited execution."""

        class RateLimitedExecutor(MockExecutor):
            async def is_close_to_rate_limit(self) -> bool:
                return True

            async def get_remaining_seconds_until_rate_limit(self) -> float:
                return 1.0

        execution_manager.register_executor(RateLimitedExecutor)

        with patch.object(execution_manager, "post_run_log") as mock_log:
            with patch.object(execution_manager, "acknowledge_run"):
                await execution_manager._execute_run(mock_action_run_task)
                mock_log.assert_called_with(
                    mock_action_run_task.run.id,
                    "Delayed due to low remaining rate limit. Will attempt to re-run in 1.0 seconds",
                )

    @pytest.mark.asyncio
    async def test_execute_run_already_acknowledged(
        self, execution_manager, mock_action_run_task
    ):
        """Test handling of already acknowledged run."""
        execution_manager.register_executor(MockExecutor)

        with patch.object(execution_manager, "acknowledge_run") as mock_acknowledge:
            mock_acknowledge.side_effect = RunAlreadyAcknowledgedError()
            await execution_manager._execute_run(mock_action_run_task)
            mock_acknowledge.assert_called_once_with(mock_action_run_task.run.id)

    @pytest.mark.asyncio
    async def test_execute_run_failure(self, execution_manager, mock_action_run_task):
        """Test handling of execution failure."""

        class FailingExecutor(MockExecutor):
            async def execute(self, payload):
                raise ValueError("Test error")

        execution_manager.register_executor(FailingExecutor)

        with patch.object(execution_manager, "acknowledge_run"):
            with patch.object(execution_manager, "patch_run") as mock_patch:
                with pytest.raises(ValueError, match="Test error"):
                    await execution_manager._execute_run(mock_action_run_task)

                mock_patch.assert_called_once_with(
                    mock_action_run_task.run.id,
                    {"summary": "Test error", "status": RunStatus.FAILURE},
                )

    @pytest.mark.asyncio
    async def test_execute_run_missing_executor(
        self, execution_manager, mock_action_run_task
    ):
        """Test handling of missing executor."""
        with pytest.raises(Exception, match="No executor registered for action"):
            await execution_manager._execute_run(mock_action_run_task)

    @pytest.mark.asyncio
    async def test_partition_queue_handling(self, execution_manager):
        """Test handling of partitioned queues."""
        execution_manager.register_executor(MockPartitionedExecutor)

        run = ActionRun(
            id="test-run-id",
            action=MagicMock(name="test_partitioned_action"),
            payload={"oceanExecution": {"partition_key": "test_partition"}},
            status=RunStatus.PENDING,
        )

        task = ActionRunTask(
            visibility_expiration_timestamp=datetime.now() + timedelta(minutes=5),
            run=run,
        )

        await execution_manager._add_run_to_queue(
            run,
            execution_manager._partition_queues.setdefault(
                "test_partition", execution_manager._global_queue.__class__()
            ),
            "test_partition",
            task.visibility_expiration_timestamp,
        )

        assert "test_partition" in execution_manager._partition_queues
        assert await execution_manager._partition_queues["test_partition"].size() == 1

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, execution_manager):
        """Test graceful shutdown of execution manager."""
        # Start processing
        await execution_manager.start_processing_action_runs()

        # Verify tasks are created
        assert execution_manager._polling_task is not None
        assert execution_manager._timeout_task is not None
        assert len(execution_manager._workers_pool) > 0

        # Shutdown
        await execution_manager.shutdown()

        # Verify tasks are cancelled
        assert execution_manager._polling_task.cancelled()
        assert execution_manager._timeout_task.cancelled()
        assert all(task.cancelled() for task in execution_manager._workers_pool)

    @pytest.mark.asyncio
    async def test_queue_high_watermark(self, execution_manager):
        """Test queue high watermark behavior."""
        execution_manager._high_watermark = 2

        # Add runs until high watermark
        run1 = ActionRun(
            id="run1",
            action=MagicMock(name="test_action"),
            payload={"oceanExecution": {}},
            status=RunStatus.PENDING,
        )
        run2 = ActionRun(
            id="run2",
            action=MagicMock(name="test_action"),
            payload={"oceanExecution": {}},
            status=RunStatus.PENDING,
        )

        expiration = datetime.now() + timedelta(minutes=5)
        await execution_manager._add_run_to_queue(
            run1, execution_manager._global_queue, GLOBAL_SOURCE, expiration
        )
        await execution_manager._add_run_to_queue(
            run2, execution_manager._global_queue, GLOBAL_SOURCE, expiration
        )

        # Verify queue size is at high watermark
        assert await execution_manager._get_queues_size() == 2

        # This should wait due to high watermark
        with patch("asyncio.sleep") as mock_sleep:
            await execution_manager._poll_action_runs()
            mock_sleep.assert_called_once_with(
                execution_manager._poll_check_interval_seconds
            )

    @pytest.mark.asyncio
    async def test_lock_timeout(self, execution_manager):
        """Test lock timeout behavior."""
        # Set a short lock timeout
        execution_manager._lock_timeout_seconds = 0.1

        # Lock a queue
        queue_name = "test_queue"
        assert execution_manager._try_lock(queue_name) is True

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Run timeout check
        await execution_manager._background_timeout_check()

        # Verify lock was released
        assert queue_name not in execution_manager._locked
        assert queue_name not in execution_manager._lock_timestamps
