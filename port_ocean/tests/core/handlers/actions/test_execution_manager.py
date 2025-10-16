from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from fastapi import APIRouter, FastAPI
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
    InvocationType,
    RunStatus,
)
from port_ocean.exceptions.execution_manager import (
    DuplicateActionExecutorError,
    RunAlreadyAcknowledgedError,
)
from port_ocean.ocean import Ocean
from port_ocean.utils.signal import SignalHandler


def generate_mock_action_run() -> ActionRun[IntegrationActionInvocationPayload]:
    return ActionRun(
        id="test-run-id",
        action=MagicMock(name="bla"),
        payload=IntegrationActionInvocationPayload(
            type=InvocationType.INTEGRATION_ACTION,
            installationId="test-installation-id",
            actionType="test_action",
            integrationActionExecutionProperties={},
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
        runs_buffer_high_watermark=100,
        poll_check_interval_seconds=5,
        max_wait_seconds_before_shutdown=30,
    )


@pytest.fixture
def execution_manager(
    mock_webhook_manager: MagicMock,
    mock_signal_handler: MagicMock,
    mock_test_executor: MagicMock,
) -> ExecutionManager:
    execution_manager = ExecutionManager(
        webhook_manager=mock_webhook_manager,
        signal_handler=mock_signal_handler,
        runs_buffer_high_watermark=100,
        poll_check_interval_seconds=5,
        max_wait_seconds_before_shutdown=30,
    )
    execution_manager.register_executor(mock_test_executor)
    execution_manager._actions_executors = {
        mock_test_executor.ACTION_NAME: mock_test_executor,
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
        few_seconds_away = datetime.now() + timedelta(seconds=2)
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
