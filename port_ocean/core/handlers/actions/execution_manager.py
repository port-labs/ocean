from __future__ import annotations

from typing import Dict, Type, Set

from loguru import logger

import asyncio
from integrations.github.github.webhook.registry import WEBHOOK_PATH
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.handlers.queue.local_queue import LocalQueue
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun
from port_ocean.utils.signal import SignalHandler


class ExecutionManager:
    """Orchestrates action executors, polling and their webhook handlers"""

    def __init__(
        self,
        webhook_manager: LiveEventsProcessorManager,
        signal_handler: SignalHandler,
        lock_timeout: float = 300,
    ):
        self._workers_pool = list[asyncio.Task[None]]()
        self._executors_by_action: Dict[str, Type[AbstractExecutor]] = {}
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
        if action_name in self._executors_by_action:
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

        self._executors_by_action[action_name] = executor_cls
        logger.info("Registered action executor", action=action_name)

    async def start_processing_action_runs(self) -> None:
        """Start polling and processing action runs for all registered actions."""
        flags = await ocean.port_client.get_organization_feature_flags()
        if "OCEAN_EXECUTION_AGENT_ELIGIBLE" not in flags:
            logger.warning(
                "Execution agent is not allowed for your organization, skipping execution agent setup"
            )
            return

    async def shutdown(self) -> None:
        """Gracefully shutdown poller and all action queue workers."""
        logger.warning("Shutting down execution manager")
        pass
