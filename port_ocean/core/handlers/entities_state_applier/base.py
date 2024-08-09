from abc import abstractmethod

from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import EntityDiff


class BaseEntitiesStateApplier(BaseHandler):
    """Abstract base class for applying and managing changes to entities' state.

    This class defines abstract methods for applying changes, deleting entities, upserting entities,
    and deleting entity changes based on a provided user agent.

    Attributes:
        context (PortOceanContext): The context to be used during state application.
    """

    @abstractmethod
    async def apply_diff(
        self,
        entities: EntityDiff,
        user_agent: UserAgentType,
    ) -> None:
        """Apply the specified entity differences to the state.

        Args:
            entities (EntityDiff): The differences to be applied.
            user_agent (UserAgentType): The user agent responsible for the changes.
        """
        pass

    @abstractmethod
    async def delete_diff(
        self,
        entities: EntityDiff,
        user_agent: UserAgentType,
    ) -> None:
        """Delete the specified entity differences from the state.

        Args:
            entities (EntityDiff): The differences to be deleted.
            user_agent (UserAgentType): The user agent responsible for the deletion.
        """
        pass

    @abstractmethod
    async def upsert(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> list[Entity]:
        """Upsert (insert or update) the given entities into the state.

        Args:
            entities (list[Entity]): The entities to be upserted.
            user_agent_type (UserAgentType): The user agent responsible for the upsert.

        Returns:
            list[Entity]: The upserted entities.
        """
        pass

    @abstractmethod
    async def delete(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        """Delete the specified entities from the state.

        Args:
            entities (list[Entity]): The entities to be deleted.
            user_agent_type (UserAgentType): The user agent responsible for the deletion.
        """
