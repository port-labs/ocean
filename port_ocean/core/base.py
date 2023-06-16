from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from port_ocean.context.integration import PortOceanContext


class BaseWithContext:
    def __init__(self, context: "PortOceanContext"):
        self.context = context
