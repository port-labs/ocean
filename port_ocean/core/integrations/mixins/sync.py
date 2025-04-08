from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.ocean import ocean
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    EntityDiff,
)


class SyncMixin(HandlerMixin):
    """Mixin class for synchronization of constructed entities.

    This mixin class extends the functionality of HandlerMixin to provide methods for updating,
    registering, unregistering, and syncing entities state changes.

    Note:
        Entities are constructed entities using the Entity class
    """

    def __init__(self) -> None:
        HandlerMixin.__init__(self)

    async def update_diff(
        self,
        desired_state: EntityDiff,
        user_agent_type: UserAgentType,
    ) -> None:
        """Update the state difference between two list of entities.

        - Any entities that are in the `before` state but not in the `after` state will be unregistered.
        - Any entities that are in the `after` state but not in the `before` state will be registered.
        - Any entities that are in both the `before` and `after` state will be synced.

        Args:
            desired_state (EntityDiff): The desired state difference of entities.
            user_agent_type (UserAgentType): The type of user agent.

        Raises:
            IntegrationNotStartedException: If EntitiesStateApplier class is not initialized.
        """
        await self.entities_state_applier.apply_diff(
            {"before": desired_state["before"], "after": desired_state["after"]},
            user_agent_type,
        )

    async def register(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType,
    ) -> None:
        """Upsert entities into Port.

        Args:
            entities (list[Entity]): List of entities to be registered.
            user_agent_type (UserAgentType): The type of user agent.

        Raises:
            IntegrationNotStartedException: If EntitiesStateApplier class is not initialized.
        """
        await self.entities_state_applier.upsert(entities, user_agent_type)
        logger.info("Finished registering change")

    async def unregister(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        """Delete entities from Port.

        Args:
            entities (list[Entity]): List of entities to be unregistered.
            user_agent_type (UserAgentType): The type of user agent.

        Raises:
            IntegrationNotStartedException: If EntitiesStateApplier class is not initialized.
        """
        await self.entities_state_applier.delete(entities, user_agent_type)
        logger.info("Finished unregistering change")

    async def sync(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType,
    ) -> None:
        """Synchronize entities' states according to the state in Port.

        The integration fetches the current state of the entities in Port according to the given user_agent_type and
        compares it to the given desired state. The integration then create/updates/delete the entities to match the
        desired state.

        Args:
            entities (list[Entity]): List of entities to be synced.
            user_agent_type (UserAgentType): The type of user agent.

        Raises:
            IntegrationNotStartedException: If EntitiesStateApplier class is not initialized.
        """
        entities_at_port = await ocean.port_client.search_entities(user_agent_type)
        app_config = await self.port_app_config_handler.get_port_app_config()

        modified_entities = await self.entities_state_applier.upsert(
            entities, user_agent_type
        )
        await self.entities_state_applier.delete_diff(
            {"before": entities_at_port, "after": modified_entities}, user_agent_type, app_config.get_entity_deletion_threshold()
        )

        logger.info("Finished syncing change")
