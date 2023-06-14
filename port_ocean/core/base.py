from port_ocean.context.integration import PortOceanContext


class BaseWithContext:
    def __init__(self, context: PortOceanContext):
        self.context = context
