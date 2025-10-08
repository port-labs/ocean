from __future__ import annotations

import threading
from typing import Dict, Type, Set, Optional, List
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
import httpx
from port_ocean.core.models import ActionRun, RunStatus
import asyncio
import time
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.handlers.queue.local_queue import LocalQueue
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationFeatureFlag
from port_ocean.utils.signal import SignalHandler
from port_ocean.utils.repeat import repeat_every


GLOBAL_SOURCE = "__global__"


class ExecutionManager(ActionsClientMixin):
    """Orchestrates action executors, polling and their webhook handlers"""

    def __init__(
        self,
        webhook_manager: LiveEventsProcessorManager,
        signal_handler: SignalHandler,
    ):
        self._polling_task: asyncio.Task[None] | None = None
        self._workers_pool: set[asyncio.Task[None]] = set()
        self._actions_executors: Dict[str, Type[AbstractExecutor]] = {}
        self._global_queue = LocalQueue[ActionRun]()
        self._partition_queues: Dict[str, AbstractQueue[ActionRun]] = {}
        self._locked: Set[str] = set()
        self._lock_timestamps: Dict[str, float] = {}
        self._webhook_manager = webhook_manager
        self._timeout_task: Optional[asyncio.Task[None]] = None
        self._active_sources = LocalQueue()
        self._queue_state_lock = asyncio.Lock()

        signal_handler.register(self.shutdown)

    def register_executor(self, executor_cls: Type[AbstractExecutor]) -> None:
        """
        Register an executor implementation.
        """
        action_name = executor_cls.ACTION_NAME
        if action_name in self._actions_executors:
            raise ValueError(f"Executor for action '{action_name}' already registered")

        webhook_processor_cls = executor_cls.WEBHOOK_PROCESSOR_CLASS
        if webhook_processor_cls:
            self._webhook_manager.register_processor(
                executor_cls.WEBHOOK_PATH,
                webhook_processor_cls,
                WebhookProcessorType.ACTION,
            )
            logger.info(
                "Registered executor webhook processor",
                action=action_name,
                webhook_path=executor_cls.WEBHOOK_PATH,
            )

        self._actions_executors[action_name] = executor_cls
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

        repeated_polling_task = repeat_every(
            seconds=ocean.config.execution_agent.polling_interval_seconds
        )(
            lambda: threading.Thread(
                target=lambda: asyncio.run_coroutine_threadsafe(
                    self._poll_action_runs(), asyncio.get_event_loop()
                )
            ).start()
        )
        self._polling_task = asyncio.create_task(repeated_polling_task)
        self._timeout_task = asyncio.create_task(self._background_timeout_check())

        workers_count = max(1, ocean.config.execution_agent.workers_count)
        for worker_index in range(workers_count):
            task = asyncio.create_task(self._process_actions_runs(worker_index))
            self._workers_pool.add(task)
            task.add_done_callback(self._workers_pool.discard)

    def _extract_partition_key(self, run: ActionRun, partition_key: str) -> str:
        """
        Extract the partition key from a run's payload.
        """
        invocation_payload = run.payload.oceanExecution
        if hasattr(invocation_payload, partition_key):
            return getattr(invocation_payload, partition_key)

        raise ValueError(
            f"Partition key '{partition_key}' not found in invocation payload"
        )

    async def _add_run_to_queue(
        self, run: ActionRun, queue: AbstractQueue[ActionRun], queue_name: str
    ) -> None:
        """
        Add a run to the queue.
        """
        was_empty = await queue.size() == 0
        await queue.put(run)
        if was_empty:
            async with self._queue_state_lock:
                await self._active_sources.put(queue_name)

    async def _poll_action_runs(self):
        """
        Poll action runs for all registered actions.
        """
        try:
            runs = await self.get_pending_runs(
                limit=ocean.config.execution_agent.max_runs_per_poll
            )

            for run in runs:
                action_name = run.action.name
                if action_name not in self._actions_executors:
                    logger.warning(
                        "No Executors registered to handle this action, skipping run...",
                        action=action_name,
                        run=run.id,
                    )
                    continue

                partition_key = self._actions_executors[action_name].PARTITION_KEY
                if not partition_key:
                    await self._add_run_to_queue(run, self._global_queue, GLOBAL_SOURCE)
                    continue

                partition_name = self._extract_partition_key(run, partition_key)
                if partition_name not in self._partition_queues:
                    self._partition_queues[partition_name] = LocalQueue()
                await self._add_run_to_queue(
                    run,
                    self._partition_queues[partition_name],
                    partition_name,
                )
        except asyncio.CancelledError:
            pass

    async def _background_timeout_check(self) -> None:
        """
        Periodically release locks that have timed out for fairness.
        """
        while True:
            try:
                await asyncio.sleep(self.lock_timeout_seconds / 4)
                now = time.time()
                expired: List[str] = []
                for key, ts in list(self._lock_timestamps.items()):
                    if now - ts > self.lock_timeout_seconds:
                        expired.append(key)
                        self._unlock(key)
                if expired:
                    logger.warning("Released expired locks", keys=expired)
            except asyncio.CancelledError:
                break

    def _try_lock(self, key: str) -> bool:
        if key in self._locked:
            return False
        self._locked.add(key)
        self._lock_timestamps[key] = time.time()
        return True

    def _unlock(self, key: str) -> None:
        self._locked.discard(key)
        self._lock_timestamps.pop(key, None)

    async def _handle_global_queue_once(self):
        if await self._global_queue.size() == 0:
            return

        async with self._queue_state_lock:
            await self._active_sources.put(GLOBAL_SOURCE)

        try:
            run = await self._global_queue.get()
            await self._execute_run(run)
        finally:
            await self._global_queue.commit()

    async def _handle_partition_queue_once(self, partition_name: str):
        """
        Try to process a single run from the given partition queue.
        Returns True if work was done, False otherwise.
        """
        queue = self._partition_queues[partition_name]
        if await queue.size() == 0:
            return

        queue_lock_key = f"queue:{partition_name}"
        successfully_locked = self._try_lock(queue_lock_key)
        if not successfully_locked:
            return

        try:
            run = await queue.get()
            await self._execute_run(run)
        finally:
            await queue.commit()
            self._unlock(queue_lock_key)
            async with self._queue_state_lock:
                await self._active_sources.put(partition_name)

    async def _process_actions_runs(self) -> None:
        """
        Round-robin worker across global queue and partition queues.
        """
        try:
            while True:
                source = await self._active_sources.get()
                try:
                    if source == GLOBAL_SOURCE:
                        await self._handle_global_queue_once()
                    else:
                        await self._handle_partition_queue_once(source)
                except Exception:
                    logger.exception("Worker processing error", source=source)
        except asyncio.CancelledError:
            pass

    async def _execute_run(self, run: ActionRun) -> None:
        """
        Execute a run using its registered executor.
        """
        try:
            executor_cls = self._actions_executors.get(run.action.name)
            if executor_cls is None:
                raise Exception("No executor registered for action")

            executor = executor_cls()
            # TODO: check if close to rate limit
            # TODO: if close to rate limit, de-ack the run and sleep for the remaining time,
            # after that, put the run back in the queue
            await executor.execute(run.payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # TODO: de-ack the run and sleep for the remaining time,
                # after that, put the run back in the queue
                pass
        except Exception as e:
            logger.exception("Error executing run", run=run.id, action=run.action.name)
            await self.patch_run(
                run.id, {"summary": str(e), "status": RunStatus.FAILURE}
            )
            raise e

    async def shutdown(self) -> None:
        """
        Gracefully shutdown poller and all action queue workers.
        """
        logger.warning("Shutting down execution manager")
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

        for task in list(self._workers_pool):
            if task and not task.done():
                task.cancel()
        for task in list(self._workers_pool):
            try:
                await task
            except asyncio.CancelledError:
                pass
