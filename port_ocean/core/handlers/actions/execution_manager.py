from __future__ import annotations

from typing import Dict, Type, Set

from loguru import logger

import asyncio
from integrations.github.github.webhook.registry import WEBHOOK_PATH
from port_ocean.clients.port.mixins.actions import ActionsClientMixin
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.handlers.queue.local_queue import LocalQueue
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, OceanExecution
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
        self._should_poll_more_runs = asyncio.Condition()
        self._workers_pool = list[asyncio.Task[None]]()
        self._actions_executors: Dict[str, Type[AbstractExecutor]] = {}
        self._global_queue = LocalQueue()
        self._partition_queues: Dict[str, AbstractQueue[ActionRun]] = {}
        self._locked: Set[str] = set()
        self._queue_not_empty = asyncio.Condition()
        self.lock_timeout = lock_timeout
        self._lock_timestamps: Dict[str, float] = {}
        self._webhook_manager = webhook_manager

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
        if "OCEAN_EXECUTION_AGENT_ELIGIBLE" not in flags:
            logger.warning(
                "Execution agent is not allowed for your organization, skipping execution agent setup"
            )
            return

        self._polling_task = asyncio.create_task(self._poll_action_runs())

    def _extract_partition_key(
        self, invocation_settings: OceanExecution, partition_key: str
    ) -> str:
        """
        Extract the partition key from a invocation settings.
        """
        if not hasattr(invocation_settings, partition_key):
            raise ValueError(
                f"Could not determine partition key for action {invocation_settings.action}"
            )
        return getattr(invocation_settings, partition_key)

    async def _add_to_partition_queue(self, run: ActionRun, partition_key: str) -> None:
        """
        Add a run to the partition queue.
        """
        partition_name = self._extract_partition_key(
            run.payload.oceanExecution, partition_key
        )
        if partition_name not in self._partition_queues:
            self._partition_queues[partition_name] = LocalQueue()
        await self._partition_queues[partition_name].put(run)

    async def _poll_action_runs(self):
        """
        Poll action runs for all registered actions.
        """
        while True:
            await self._should_poll_more_runs.wait()
            runs = await self.get_pending_runs(
                limit=ocean.config.execution_agent.max_runs_per_poll
            )
            for run in runs:
                if run.action.name not in self._actions_executors:
                    logger.warning(
                        "No Executors registered to handle this action, skipping run...",
                        action=run.action.name,
                        run=run.id,
                    )
                    continue

                partition_key = self._actions_executors[run.action.name].partition_key()
                if partition_key is not None:
                    await self._add_to_partition_queue(run, partition_key)
                else:
                    await self._global_queue.put(run)

    async def shutdown(self) -> None:
        """
        Gracefully shutdown poller and all action queue workers.
        """
        logger.warning("Shutting down execution manager")
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
