from typing import List

from port_ocean.context.integration import ocean
from port_ocean.core.manipulation.base import PortDiff
from port_ocean.core.transport.base import BaseTransport


class HttpPortTransport(BaseTransport):
    async def register(self, changes: List[PortDiff]) -> None:
        await ocean.port_client.register(changes)
