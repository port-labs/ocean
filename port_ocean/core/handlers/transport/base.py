from abc import abstractmethod
from typing import List

from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.manipulation.base import PortDiff


class BaseTransport(BaseWithContext):
    @abstractmethod
    async def update_diff(self, changes: List[PortDiff]) -> None:
        pass
