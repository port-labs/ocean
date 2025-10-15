from datetime import datetime, timedelta
from typing import Dict, Set
from loguru import logger
from pydantic import BaseModel
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
import asyncio
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.handlers.queue.local_queue import LocalQueue
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationFeatureFlag
from port_ocean.exceptions.execution_manager import (
    DuplicateActionExecutorError,
    PartitionKeyNotFoundError,
    RunAlreadyAcknowledgedError,
)
from port_ocean.utils.signal import SignalHandler


GLOBAL_SOURCE = "__global__"


class ActionRunTask(BaseModel):
    visibility_expiration_timestamp: datetime
    queue_name: str
    run: ActionRun[IntegrationActionInvocationPayload]


class ExecutionManager:
    """Orchestrates action executors, polling and their webhook handlers"""

    def __init__(
        self,
        webhook_manager: LiveEventsProcessorManager,
        signal_handler: SignalHandler,
        runs_buffer_high_watermark: int,
        poll_check_interval_seconds: int,
        max_wait_seconds_before_shutdown: float,
    ):
        self._webhook_manager = webhook_manager
        self._polling_task: asyncio.Task[None] | None = None
        self._workers_pool: set[asyncio.Task[None]] = set()
        self._actions_executors: Dict[str, AbstractExecutor] = {}
        self._is_shutting_down = asyncio.Event()
        self._global_queue = LocalQueue[ActionRunTask]()
        self._partition_queues: Dict[str, AbstractQueue[ActionRunTask]] = {}
        self._deduplication_set: Set[str] = set()
        self._queues_locks: Dict[str, asyncio.Lock] = {GLOBAL_SOURCE: asyncio.Lock()}
        self._active_sources: AbstractQueue[str] = LocalQueue[str]()
        self._high_watermark: int = runs_buffer_high_watermark
        self._poll_check_interval_seconds: int = poll_check_interval_seconds
        self._max_wait_seconds_before_shutdown: float = max_wait_seconds_before_shutdown

        signal_handler.register(self.shutdown)

    def register_executor(self, executor: AbstractExecutor) -> None:
        """
        Register an executor implementation.
        """
        action_name = executor.ACTION_NAME
        if action_name in self._actions_executors:
            raise DuplicateActionExecutorError(
                f"Executor for action '{action_name}' is already registered"
            )

        webhook_processor_cls = executor.WEBHOOK_PROCESSOR_CLASS
        if webhook_processor_cls:
            self._webhook_manager.register_processor(
                executor.WEBHOOK_PATH,
                webhook_processor_cls,
            )
            logger.info(
                "Registered executor webhook processor",
                action=action_name,
                webhook_path=executor.WEBHOOK_PATH,
            )

        self._actions_executors[action_name] = executor
        logger.info("Registered action executor", action=action_name)

    async def start_processing_action_runs(self):
        """
        Start polling and processing action runs for all registered actions.
        """
        flags = await ocean.port_client.get_organization_feature_flags()
        if IntegrationFeatureFlag.OCEAN_EXECUTION_AGENT_ELIGIBLE not in flags:
            logger.warning(
                "Execution agent is not allowed for your organization, skipping execution agent setup"
            )
            return

        self._polling_task = asyncio.create_task(self._poll_action_runs())

        workers_count = max(1, ocean.config.execution_agent.workers_count)
        for _ in range(workers_count):
            task = asyncio.create_task(self._process_actions_runs())
            self._workers_pool.add(task)
            task.add_done_callback(self._workers_pool.discard)

    async def _poll_action_runs(self):
        """
        Poll action runs for all registered actions.
        Respects high watermark for queue size management.
        """
        while True:
            try:
                queues_size = await self._get_queues_size()
                if queues_size >= self._high_watermark:
                    logger.warning(
                        "Queue size at high watermark, waiting for processing to catch up",
                        current_size=queues_size,
                        high_watermark=self._high_watermark,
                    )
                    await asyncio.sleep(self._poll_check_interval_seconds)
                    continue

                poll_limit = self._high_watermark - queues_size
                runs: list[ActionRun[IntegrationActionInvocationPayload]] = (
                    await ocean.port_client.get_pending_runs(
                        limit=poll_limit,
                        visibility_timeout_seconds=ocean.config.execution_agent.visibility_timeout_seconds,
                    )
                )

                if not runs:
                    logger.info(
                        "No runs to process, waiting for next poll",
                        current_size=queues_size,
                        high_watermark=self._high_watermark,
                    )
                    await asyncio.sleep(self._poll_check_interval_seconds)
                    continue

                visibility_expiration_timestamp = datetime.now() + timedelta(
                    seconds=ocean.config.execution_agent.visibility_timeout_seconds
                )

                for run in runs:
                    action_type = run.payload.actionType
                    if action_type not in self._actions_executors:
                        logger.warning(
                            "No Executors registered to handle this action, skipping run...",
                            action_type=action_type,
                            run=run.id,
                        )
                        continue

                    partition_key = self._actions_executors[action_type].PARTITION_KEY
                    if not partition_key:
                        await self._add_run_to_queue(
                            run,
                            self._global_queue,
                            GLOBAL_SOURCE,
                            visibility_expiration_timestamp,
                        )
                        continue

                    partition_key = self._extract_partition_key(run, partition_key)
                    partition_name = f"{action_type}:{partition_key}"
                    if partition_name not in self._partition_queues:
                        self._partition_queues[partition_name] = LocalQueue()
                        self._queues_locks[partition_name] = asyncio.Lock()
                    await self._add_run_to_queue(
                        run,
                        self._partition_queues[partition_name],
                        partition_name,
                        visibility_expiration_timestamp,
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(
                    "Unexpected error in poll action runs, will attempt to re-poll",
                    error=e,
                )

    async def _get_queues_size(self) -> int:
        """
        Get the total size of all queues (global and partition queues).
        """
        global_size = await self._global_queue.size()
        partition_sizes = []
        for queue in self._partition_queues.values():
            partition_sizes.append(await queue.size())
        return global_size + sum(partition_sizes)

    async def _add_run_to_queue(
        self,
        run: ActionRun[IntegrationActionInvocationPayload],
        queue: AbstractQueue[ActionRunTask],
        queue_name: str,
        visibility_expiration_timestamp: datetime,
    ) -> None:
        """
        Add a run to the queue.
        """
        async with self._queues_locks[queue_name]:
            self._deduplication_set.add(run.id)
            await queue.put(
                ActionRunTask(
                    visibility_expiration_timestamp=visibility_expiration_timestamp,
                    queue_name=queue_name,
                    run=run,
                )
            )
        await self._add_source_if_not_empty(queue_name)

    async def _add_source_if_not_empty(self, source_name: str) -> None:
        """
        Add a source to the active sources if the queue is not empty.
        """
        async with self._queues_locks[source_name]:
            queue = (
                self._global_queue
                if source_name == GLOBAL_SOURCE
                else self._partition_queues[source_name]
            )
            if await queue.size() > 0:
                await self._active_sources.put(source_name)

    def _extract_partition_key(
        self, run: ActionRun[IntegrationActionInvocationPayload], partition_key: str
    ) -> str:
        """
        Extract the partition key from a run's payload.
        """
        value = run.payload.integrationActionExecutionProperties.get(partition_key)
        if value:
            return value

        raise PartitionKeyNotFoundError(
            f"Partition key '{partition_key}' not found in invocation payload"
        )

    async def _process_actions_runs(self) -> None:
        """
        Round-robin worker across global and partitions queues.
        """
        while not self._is_shutting_down.is_set():
            try:
                source = await self._active_sources.get()

                if source == GLOBAL_SOURCE:
                    await self._handle_global_queue_once()
                else:
                    await self._handle_partition_queue_once(source)
            except Exception as e:
                logger.exception("Worker processing error", source=source, error=e)

    async def _handle_global_queue_once(self):
        try:
            async with self._queues_locks[GLOBAL_SOURCE]:
                run_task = await self._global_queue.get()
                if run_task.run.id in self._deduplication_set:
                    self._deduplication_set.remove(run_task.run.id)

            await self._add_source_if_not_empty(GLOBAL_SOURCE)
            await self._execute_run(run_task.run)
        finally:
            await self._global_queue.commit()

    async def _handle_partition_queue_once(self, partition_name: str):
        """
        Try to process a single run from the given partition queue.
        Returns True if work was done, False otherwise.
        """
        queue = self._partition_queues[partition_name]
        try:
            async with self._queues_locks[partition_name]:
                run_task = await queue.get()
                if run_task.run.id in self._deduplication_set:
                    self._deduplication_set.remove(run_task.run.id)
            await self._execute_run(run_task)
        finally:
            await queue.commit()
            await self._add_source_if_not_empty(partition_name)

    async def _execute_run(self, run_task: ActionRunTask) -> None:
        """
        Execute a run using its registered executor.
        """
        try:
            async with self._queues_locks[run_task.queue_name]:
                should_skip_execution = (
                    run_task.visibility_expiration_timestamp < datetime.now()
                    and run_task.run.id in self._deduplication_set
                )
            if should_skip_execution:
                logger.info(
                    "Run visibility has already expired and is being deduplicated, skipping execution",
                    run=run_task.run.id,
                )
                return

            executor = self._actions_executors[run_task.run.payload.actionType]
            while await executor.is_close_to_rate_limit():
                await ocean.port_client.post_run_log(
                    run_task.run.id,
                    f"Delayed due to low remaining rate limit. Will attempt to re-run in {executor.get_remaining_seconds_until_rate_limit()} seconds",
                )
                await asyncio.sleep(
                    await executor.get_remaining_seconds_until_rate_limit()
                )

            await ocean.port_client.acknowledge_run(run_task.run.id)
            logger.debug("Run acknowledged successfully", run=run_task.run.id)
            await executor.execute(run_task.run)
        except RunAlreadyAcknowledgedError:
            logger.warning(
                "Run already being processed by another worker, skipping execution",
                run=run_task.run.id,
            )
            return
        except Exception as e:
            logger.error(
                "Error executing run",
                error=e,
                run=run_task.run.id,
                action=run_task.run.payload.actionType,
            )
            await ocean.port_client.patch_run(
                run_task.run.id, {"summary": str(e), "status": RunStatus.FAILURE}
            )

    async def _gracefully_cancel_task(self, task: asyncio.Task[None]) -> None:
        """
        Gracefully cancel a task.
        """
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        """
        Gracefully shutdown poller and all action queue workers.
        """
        logger.warning("Shutting down execution manager")

        self._is_shutting_down.set()
        logger.info("Waiting for workers to complete their current tasks...")

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self._gracefully_cancel_task(self._polling_task),
                    *(worker for worker in self._workers_pool),
                ),
                timeout=self._max_wait_seconds_before_shutdown,
            )
            logger.info("All workers completed gracefully")
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for workers to complete")
