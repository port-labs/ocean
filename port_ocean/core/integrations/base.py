import asyncio
from typing import Any

from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event_context, TriggerType
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins.sync import SyncRawMixin, SyncMixin
from port_ocean.core.models import Entity
from port_ocean.core.trigger_channel.factory import TriggerChannelFactory


class BaseIntegration(SyncRawMixin, SyncMixin):
    def __init__(self, context: PortOceanContext):
        SyncRawMixin.__init__(self)
        SyncMixin.__init__(self)
        self.started = False
        self.context = context
        self.trigger_channel = TriggerChannelFactory(
            context,
            self.context.config.integration.identifier,
            {"on_action": self.trigger_action, "on_resync": self.sync_all},
        )

    async def _sync_new_in_batches(
        self, resource_config: ResourceConfig, user_agent_type: UserAgentType
    ) -> list[Entity]:
        resource, results = await self._get_resource_raw_results(resource_config)

        tasks = []

        batch_size = self.context.config.batch_work_size or len(results)
        for batch in [
            results[i : i + batch_size] for i in range(0, len(results), batch_size)
        ]:
            tasks.append(self._register_resource_raw(resource, batch, user_agent_type))
        entities = await asyncio.gather(*tasks)
        return sum(entities, [])

    async def start(self) -> None:
        logger.info("Starting integration")
        if self.started:
            raise Exception("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self.initialize_handlers()

        logger.info("Initializing integration at port")
        await self.context.port_client.initiate_integration(
            self.context.config.integration.identifier,
            self.context.config.integration.type,
            self.context.config.trigger_channel.to_request(),
        )

        logger.info("Initializing trigger channel")
        await self.trigger_channel.create_trigger_channel()

        self.started = True

        async with event_context("start", trigger_type="machine"):
            await asyncio.gather(
                *(listener() for listener in self.event_strategy["start"])
            )

    async def trigger_action(self, data: dict[Any, Any]) -> None:
        raise NotImplementedError("trigger_action is not implemented")

    async def sync_all(
        self,
        _: dict[Any, Any] | None = None,
        trigger_type: TriggerType = "machine",
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        logger.info("Resync was triggered")

        async with event_context("resync", trigger_type=trigger_type):
            app_config = await self.port_app_config_handler.get_port_app_config()

            created_entities = await asyncio.gather(
                *(
                    self._sync_new_in_batches(resource, user_agent_type)
                    for resource in app_config.resources
                )
            )

            await self.transport.delete_non_existing(
                sum(created_entities, []), user_agent_type
            )

            logger.info("Resync was finished")
