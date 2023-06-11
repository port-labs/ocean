import logging
from typing import List

from port_ocean.core.manipulation.base import PortDiff
from port_ocean.core.port.base import BasePortClient

logger = logging.getLogger(__name__)


class PortClient(BasePortClient):
    async def register(self, changes: List[PortDiff]) -> None:
        pass
