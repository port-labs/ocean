from abc import abstractmethod

from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.base import BaseWithContext
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import EntityDiff


class BaseEntitiesStateApplier(BaseWithContext):
    @abstractmethod
    async def apply_diff(
        self,
        entities: EntityDiff,
        user_agent: UserAgentType,
    ) -> None:
        pass

    @abstractmethod
    async def delete_diff(
        self,
        entities: EntityDiff,
        user_agent: UserAgentType,
    ) -> None:
        pass

    @abstractmethod
    async def upsert(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        pass

    @abstractmethod
    async def delete(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        pass
