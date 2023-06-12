from abc import abstractmethod
from typing import List, NoReturn

from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.manipulation.base import PortDiff


class BaseTransport(BaseHandler):
    @abstractmethod
    async def update_diff(self, changes: List[PortDiff]) -> NoReturn:
        pass
