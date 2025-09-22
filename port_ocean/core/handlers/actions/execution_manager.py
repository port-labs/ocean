from __future__ import annotations

from typing import Dict, Type, Set, Optional, List

from loguru import logger
import random
from port_ocean.core.models import (
    Action,
    ActionRun,
    RunStatus,
    IntegrationInvocationPayload,
    InvocationType,
)
import asyncio
import time
from integrations.github.github.webhook.registry import WEBHOOK_PATH
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


class ExecutionManager(ActionsClientMixin):
    """Orchestrates action executors, polling and their webhook handlers"""

    def __init__(
        self,
        webhook_manager: LiveEventsProcessorManager,
        signal_handler: SignalHandler,
        lock_timeout: float = 300,
    ):
        self._polling_task: asyncio.Task[None] | None = None
        self._should_fetch_more_runs = asyncio.Condition()
        self._workers_pool: set[asyncio.Task[None]] = set()
        self._actions_executors: Dict[str, Type[AbstractExecutor]] = {}
        self._global_queue = LocalQueue()
        self._partition_queues: Dict[str, AbstractQueue[ActionRun]] = {}
        self._locked: Set[str] = set()
        self._queue_not_empty = asyncio.Condition()
        self.lock_timeout = lock_timeout
        self._lock_timestamps: Dict[str, float] = {}
        self._webhook_manager = webhook_manager
        self._timeout_task: Optional[asyncio.Task[None]] = None

        signal_handler.register(self.shutdown)

    def register_executor(self, executor_cls: Type[AbstractExecutor]) -> None:
        """
        Register an executor implementation.
        """
        action_name = executor_cls.action_name()
        if action_name in self._actions_executors:
            raise ValueError(f"Executor for action '{action_name}' already registered")

        webhook_processor_cls = executor_cls.get_webhook_processor()
        if webhook_processor_cls:
            self._webhook_manager.register_processor(
                WEBHOOK_PATH, webhook_processor_cls
            )
            logger.info(
                "Registered executor webhook processor",
                action=action_name,
                webhook_path=WEBHOOK_PATH,
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

        self._polling_task = asyncio.create_task(self._poll_action_runs())
        self._timeout_task = asyncio.create_task(self._background_timeout_check())

        workers_count = max(1, ocean.config.execution_agent.workers_count)
        for worker_index in range(workers_count):
            task = asyncio.create_task(self._process_actions(worker_index))
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

    async def _add_to_partition_queue(self, run: ActionRun, partition_key: str) -> None:
        """
        Add a run to the partition queue.
        """
        partition_name = self._extract_partition_key(run, partition_key)
        if partition_name not in self._partition_queues:
            self._partition_queues[partition_name] = LocalQueue()
        await self._partition_queues[partition_name].put(run)
        async with self._queue_not_empty:
            self._queue_not_empty.notify_all()

    async def _poll_action_runs(self):
        """
        Poll action runs for all registered actions.
        """
        while True:
            try:
                async with self._should_fetch_more_runs:
                    await self._should_fetch_more_runs.wait()

                # TODO: Uncomment this when the API is implemented
                # runs = await self.get_pending_runs(
                #     limit=ocean.config.execution_agent.max_runs_per_poll
                # )
                mock_actions = [
                    "dispatch_workflow",
                    "create_issue",
                    "create_pull_request",
                ]
                mock_actions_payloads = {
                    "dispatch_workflow": {
                        "repo": "test",
                        "workflow": "test.yml",
                        "reportWorkflowStatus": True,
                        "workflowInputs": {"param1": "value1", "param2": 1},
                    },
                    "create_issue": {"title": "test", "body": "test"},
                    "create_pull_request": {"title": "test", "body": "test"},
                }
                num_runs = random.randint(
                    2, ocean.config.execution_agent.max_runs_per_poll
                )
                runs = [
                    ActionRun(
                        id=str(i),
                        status=RunStatus.IN_PROGRESS,
                        action=Action(
                            id=f"action_{i}",
                            name=f"test_action_{i}",
                            description=f"Test action {i}",
                        ),
                        payload=IntegrationInvocationPayload(
                            type=InvocationType.OCEAN,
                            installationId=ocean.config.integration.identifier,
                            action=mock_actions[i % len(mock_actions)],
                            oceanExecution=mock_actions_payloads[
                                mock_actions[i % len(mock_actions)]
                            ],
                        ),
                    )
                    for i in range(num_runs)
                ]

                for run in runs:
                    action_name = run.action.name
                    if action_name not in self._actions_executors:
                        logger.warning(
                            "No Executors registered to handle this action, skipping run...",
                            action=action_name,
                            run=run.id,
                        )
                        continue

                    partition_key_value = self._actions_executors[
                        action_name
                    ].partition_key()
                    if partition_key_value:
                        await self._add_to_partition_queue(run, partition_key_value)
                    else:
                        await self._global_queue.put(run)

                    # TODO: Ack this run in action service
                    async with self._queue_not_empty:
                        self._queue_not_empty.notify_all()
            except asyncio.CancelledError:
                break

    async def _background_timeout_check(self) -> None:
        """
        Periodically release locks that have timed out for fairness.
        """
        while True:
            try:
                await asyncio.sleep(self.lock_timeout / 4)
                async with self._queue_not_empty:
                    now = time.time()
                    expired: List[str] = []
                    for key, ts in list(self._lock_timestamps.items()):
                        if now - ts > self.lock_timeout:
                            expired.append(key)
                            self._locked.discard(key)
                            del self._lock_timestamps[key]
                    if expired:
                        logger.warning("Released expired locks", keys=expired)
                        self._queue_not_empty.notify_all()
            except asyncio.CancelledError:
                break

    async def _try_lock(self, key: str) -> bool:
        async with self._queue_not_empty:
            if key in self._locked:
                return False
            self._locked.add(key)
            self._lock_timestamps[key] = time.time()
            return True

    async def _unlock(self, key: str) -> None:
        async with self._queue_not_empty:
            self._locked.discard(key)
            self._lock_timestamps.pop(key, None)
            self._queue_not_empty.notify_all()

    async def _request_more_runs(self) -> None:
        async with self._should_fetch_more_runs:
            self._should_fetch_more_runs.notify_all()

    async def _process_actions(self, worker_index: int) -> None:
        """
        Round-robin worker across global queue and partition queues.

        - Global queue uses task-level locks: one lock per run id
        - Partition queues use queue-level locks: one lock per partition name
        """
        next_start_index = worker_index
        while True:
            did_work = False

            # Compose fair-order source list: global marker + current partitions
            sources: List[str] = ["__global__"] + list(self._partition_queues.keys())
            if not sources:
                await self._request_more_runs()
                await asyncio.sleep(0.05)
                continue

            count = len(sources)
            for step in range(count):
                idx = (next_start_index + step) % count
                source = sources[idx]

                try:
                    if source == "__global__":
                        if await self._global_queue.size() == 0:
                            continue
                        run = await self._global_queue.get()
                        run_lock_key = f"run:{run.id}"
                        locked = await self._try_lock(run_lock_key)
                        try:
                            if not locked:
                                # Put back and skip; someone else holds the lock
                                await self._global_queue.put(run)
                                await self._global_queue.commit()
                                continue
                            did_work = True
                            await self._execute_run(run)
                            await self._global_queue.commit()
                        finally:
                            if locked:
                                await self._unlock(run_lock_key)
                    else:
                        queue = self._partition_queues.get(source)
                        if queue is None or await queue.size() == 0:
                            continue
                        queue_lock_key = f"queue:{source}"
                        locked = await self._try_lock(queue_lock_key)
                        if not locked:
                            continue
                        try:
                            run = await queue.get()
                            did_work = True
                            await self._execute_run(run)
                            await queue.commit()
                        finally:
                            await self._unlock(queue_lock_key)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.exception(
                        "Worker processing error", error=str(exc), source=source
                    )

                if did_work:
                    next_start_index = (idx + 1) % count
                    break

            if not did_work:
                await self._request_more_runs()
                await asyncio.sleep(0.05)

    async def _execute_run(self, run: ActionRun) -> None:
        """
        Execute a run using its registered executor.
        """
        try:
            executor_cls = self._actions_executors.get(run.action.name)
            if executor_cls is None:
                raise Exception("No executor registered for action")

            executor = executor_cls()
            await executor.execute(run.payload.oceanExecution.inputs)
            await self.patch_run(run.id, {"status": RunStatus.SUCCESS})
        except Exception as e:
            logger.exception("Error executing run", run=run.id, action=run.action.name)
            await self.patch_run(
                run.id, {"summary": str(e), "status": RunStatus.FAILURE}
            )

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
