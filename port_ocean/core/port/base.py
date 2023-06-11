from abc import abstractmethod
from typing import List, NoReturn

from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.core.manipulation.base import PortDiff


class BasePortClient:
    def __init__(self, config: IntegrationConfiguration):
        self.config = config

    @abstractmethod
    async def register(self, changes: List[PortDiff]) -> NoReturn:
        pass
