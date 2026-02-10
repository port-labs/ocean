import time
from typing import Dict, Set
from loguru import logger
from port_ocean.core.models import (
    ActionRun,
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
from port_ocean.exceptions.execution_manager import (
    DuplicateActionExecutorError,
    PartitionKeyNotFoundError,
    RunAlreadyAcknowledgedError,
)
from port_ocean.utils.signal import SignalHandler

RATE_LIMIT_MAX_BACKOFF_SECONDS = 10
QUEUE_GET_TIMEOUT_SECONDS = 1
GLOBAL_SOURCE = "__global__"


class ExecutionManager:
    """
    Orchestrates action executors, polling, and webhook handlers for integration actions.

    The manager uses a queue-based system with support for:
    - Global queue for non-partitioned actions
    - Partition-specific queues for actions requiring sequential execution
    - Round-robin worker distribution
    - Deduplication of runs
    - High watermark-based flow control

    Attributes:
        _webhook_manager (LiveEventsProcessorManager): Manages webhook processors for async updates
        _polling_task (asyncio.Task[None] | None): Task that polls for new action runs
        _workers_pool (set[asyncio.Task[None]]): Pool of worker tasks processing runs
        _actions_executors (Dict[str, AbstractExecutor]): Registered action executors
        _is_shutting_down (asyncio.Event): Event flag for graceful shutdown
        _global_queue (LocalQueue[ActionRun]): Queue for non-partitioned actions
        _partition_queues (Dict[str, AbstractQueue[ActionRun]]): Queues for partitioned actions
        _deduplication_set (Set[str]): Set of run IDs for deduplication
        _queues_locks (Dict[str, asyncio.Lock]): Locks for queue access synchronization
        _active_sources (AbstractQueue[str]): Queue of active sources (global or partition-specific) used for round-robin distribution of work among workers
        _workers_count (int): Number of workers to start
        _high_watermark (int): Maximum total runs in all queues
        _poll_check_interval_seconds (int): Seconds between polling attempts
        _visibility_timeout_ms (int): Visibility timeout for runs
        _max_wait_seconds_before_shutdown (float): Maximum wait time during shutdown

    Example:
        ```python
        # Create and configure execution manager
        manager = ExecutionManager(
            webhook_manager=webhook_mgr,
            signal_handler=signal_handler,
            workers_count=3,
            runs_buffer_high_watermark=1000,
            poll_check_interval_seconds=5,
            visibility_timeout_ms=30000,
            max_wait_seconds_before_shutdown=30.0
        )

        # Register action executors
        manager.register_executor(MyActionExecutor())

        # Start processing
        await manager.start_processing_action_runs()
        ```
    """

    def __init__(
        self,
        webhook_manager: LiveEventsProcessorManager,
        signal_handler: SignalHandler,
        runs_buffer_high_watermark: int,
        workers_count: int,
        poll_check_interval_seconds: int,
        visibility_timeout_ms: int,
        max_wait_seconds_before_shutdown: float,
    ):
        self._webhook_manager = webhook_manager
        self._polling_task: asyncio.Task[None] | None = None
        self._workers_pool: set[asyncio.Task[None]] = set[asyncio.Task[None]]()
        self._actions_executors: Dict[str, AbstractExecutor] = {}
        self._is_shutting_down = asyncio.Event()
        self._global_queue = LocalQueue[ActionRun]()
        self._partition_queues: Dict[str, AbstractQueue[ActionRun]] = {}
        self._deduplication_set: Set[str] = set[str]()
        self._queues_locks: Dict[str, asyncio.Lock] = {GLOBAL_SOURCE: asyncio.Lock()}
        self._active_sources: AbstractQueue[str] = LocalQueue[str]()
        self._workers_count: int = workers_count
        self._high_watermark: int = runs_buffer_high_watermark
        self._poll_check_interval_seconds: int = poll_check_interval_seconds
        self._visibility_timeout_ms: int = visibility_timeout_ms
        self._max_wait_seconds_before_shutdown: float = max_wait_seconds_before_shutdown

        signal_handler.register(self.shutdown)

    def register_executor(self, executor: AbstractExecutor) -> None:
        """
        Register an action executor with the execution manager.
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

    async def start_processing_action_runs(self) -> None:
        """
        Start polling and processing action runs for all registered actions.
        """
        if not await ocean.port_client.auth.is_machine_user():
            logger.warning(
                "Actions processing is allowed only for machine users, skipping actions processing"
            )
            return

        self._polling_task = asyncio.create_task(self._poll_action_runs())

        workers_count = max(1, self._workers_count)
        for _ in range(workers_count):
            task = asyncio.create_task(self._process_actions_runs())
            self._workers_pool.add(task)
            task.add_done_callback(self._workers_pool.discard)

    async def _poll_action_runs(self) -> None:
        """
        Poll action runs for all registered actions.
        Respects high watermark for queue size management.
        """
        while True:
            try:
                # Yield control to the event loop to handle any pending cancellation requests.
                await asyncio.sleep(0)
                queues_size = await self._get_queues_size()
                if queues_size >= self._high_watermark:
                    logger.info(
                        "Queue size at high watermark, waiting for processing to catch up",
                        current_size=queues_size,
                        high_watermark=self._high_watermark,
                    )
                    await asyncio.sleep(self._poll_check_interval_seconds)
                    continue

                poll_limit = self._high_watermark - queues_size
                runs: list[ActionRun] = await ocean.port_client.claim_pending_runs(
                    limit=poll_limit,
                    visibility_timeout_ms=self._visibility_timeout_ms,
                )

                if not runs:
                    logger.debug(
                        "No runs to process, waiting for next poll",
                        current_size=queues_size,
                        high_watermark=self._high_watermark,
                    )
                    await asyncio.sleep(self._poll_check_interval_seconds)
                    continue

                logger.info(f"Adding {len(runs)} runs to queues", runs_count=len(runs))
                for run in runs:
                    try:
                        action_type = run.payload.integrationActionType
                        if action_type not in self._actions_executors:
                            logger.warning(
                                "No Executors registered to handle this action, skipping run...",
                                action_type=action_type,
                                run_id=run.id,
                            )
                            continue

                        if run.id in self._deduplication_set:
                            logger.info(
                                "Run is already being processed, skipping...",
                                run_id=run.id,
                            )
                            continue

                        partition_key = await self._actions_executors[
                            action_type
                        ]._get_partition_key(run)

                        queue_name = (
                            GLOBAL_SOURCE
                            if not partition_key
                            else f"{action_type}:{partition_key}"
                        )
                        await self._add_run_to_queue(run, queue_name)
                    except PartitionKeyNotFoundError as e:
                        logger.warning(
                            "Partition key not found in invocation payload, skipping run...",
                            run_id=run.id,
                            action_type=action_type,
                            error=e,
                        )
                    except Exception as e:
                        logger.exception(
                            "Error adding run to queue",
                            run_id=run.id,
                            action_type=action_type,
                            error=e,
                        )
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
        run: ActionRun,
        queue_name: str,
    ) -> None:
        """
        Add a run to the queue, if the queue is empty, add the source to the active sources.
        """
        if queue_name != GLOBAL_SOURCE and queue_name not in self._partition_queues:
            self._partition_queues[queue_name] = LocalQueue[ActionRun]()
            self._queues_locks[queue_name] = asyncio.Lock()

        queue = (
            self._global_queue
            if queue_name == GLOBAL_SOURCE
            else self._partition_queues[queue_name]
        )
        async with self._queues_locks[queue_name]:
            if await queue.size() == 0:
                await self._active_sources.put(queue_name)
                self._deduplication_set.add(run.id)
            logger.info(
                f"Adding run to queue {queue_name}",
                run_id=run.id,
                queue_name=queue_name,
            )
            await queue.put(run)

    async def _add_source_if_not_empty(self, source_name: str) -> None:
        """
        Add a source back to the active sources if the queue is not empty.
        """
        async with self._queues_locks[source_name]:
            queue = (
                self._global_queue
                if source_name == GLOBAL_SOURCE
                else self._partition_queues[source_name]
            )

            queue_size = await queue.size()
            if queue_size > 0:
                logger.debug(
                    f"Adding source {source_name} back to active sources as it's not empty",
                    source_name=source_name,
                    queue_size=queue_size,
                )
                await self._active_sources.put(source_name)

    async def _process_actions_runs(self) -> None:
        """
        Round-robin worker across global and partitions queues.
        """
        while not self._is_shutting_down.is_set():
            try:
                # Enable graceful worker shutdown when there are no active sources to process
                # Using asyncio.Queue.get without a timeout would block indefinitely if active sources are empty
                try:
                    source = await asyncio.wait_for(
                        self._active_sources.get(),
                        timeout=self._max_wait_seconds_before_shutdown / 3,
                    )
                    logger.debug(
                        f"Processing run from {source} queue",
                        queue_size=await self._get_queues_size(),
                    )
                except asyncio.TimeoutError:
                    continue

                if source == GLOBAL_SOURCE:
                    await self._handle_global_queue_once()
                else:
                    await self._handle_partition_queue_once(source)
            except Exception as e:
                logger.exception("Worker processing error", source=source, error=e)

    async def _handle_global_queue_once(self) -> None:
        """
        Try to process a single run from the global queue.
        """
        try:
            async with self._queues_locks[GLOBAL_SOURCE]:
                try:
                    logger.debug("Handling run from global queue")
                    run = await asyncio.wait_for(
                        self._global_queue.get(), timeout=QUEUE_GET_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    logger.debug("Global queue is empty, skipping")
                    return

                if run.id in self._deduplication_set:
                    self._deduplication_set.remove(run.id)

            await self._add_source_if_not_empty(GLOBAL_SOURCE)
            await self._execute_run(run)
        finally:
            await self._global_queue.commit()

    async def _handle_partition_queue_once(self, partition_name: str) -> None:
        """
        Try to process a single run from the given partition queue.
        """
        queue = self._partition_queues[partition_name]
        try:
            async with self._queues_locks[partition_name]:
                try:
                    logger.debug(f"Handling run from {partition_name} queue")
                    run = await asyncio.wait_for(
                        queue.get(), timeout=QUEUE_GET_TIMEOUT_SECONDS
                    )
                    if run.id in self._deduplication_set:
                        self._deduplication_set.remove(run.id)
                except asyncio.TimeoutError:
                    logger.debug(f"Partition queue {partition_name} is empty, skipping")
                    return

            await self._execute_run(run)
        finally:
            await queue.commit()
            await self._add_source_if_not_empty(partition_name)

    async def _execute_run(self, run: ActionRun) -> None:
        """
        Execute a run using its registered executor.
        """
        with logger.contextualize(
            run_id=run.id, action=run.payload.integrationActionType
        ):
            error_summary: str | None = None
            try:
                executor = self._actions_executors[run.payload.integrationActionType]
                while (
                    await executor.is_close_to_rate_limit()
                    and not self._is_shutting_down.is_set()
                ):
                    backoff_seconds = min(
                        RATE_LIMIT_MAX_BACKOFF_SECONDS,
                        await executor.get_remaining_seconds_until_rate_limit(),
                    )
                    logger.info(
                        "Encountered rate limit, will attempt to re-run in {backoff_seconds} seconds",
                        backoff_seconds=backoff_seconds,
                    )
                    await ocean.port_client.post_run_log(
                        run.id,
                        f"Delayed due to low remaining rate limit. Will attempt to re-run in {backoff_seconds} seconds",
                    )
                    await asyncio.sleep(backoff_seconds)

                if self._is_shutting_down.is_set():
                    logger.warning(
                        "Shutting down execution manager, skipping execution"
                    )
                    return

                await ocean.port_client.acknowledge_run(run.id)
                logger.info("Run acknowledged successfully")
            except RunAlreadyAcknowledgedError:
                logger.warning(
                    "Run already being processed by another worker, skipping execution",
                )
                return
            except Exception as e:
                logger.error(
                    "Error occurred while trying to trigger run execution",
                    error=e,
                )
                error_summary = "Failed to trigger run execution"

            try:
                start_time = time.monotonic()
                await executor.execute(run)
                logger.info(
                    "Run executed successfully",
                    elapsed_ms=(time.monotonic() - start_time) * 1000,
                )
            except Exception as e:
                logger.exception("Error executing run")
                error_summary = f"Failed to execute run: {str(e)}"

            if error_summary:
                await ocean.port_client.patch_run(
                    run.id,
                    {
                        "summary": error_summary,
                        "status": RunStatus.FAILURE,
                    },
                    should_raise=False,
                )

    async def _gracefully_cancel_task(self, task: asyncio.Task[None] | None) -> None:
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
