from port_ocean.context.ocean import PortOceanContext


class BaseHandler:
    def __init__(self, context: PortOceanContext):
        self.context = context
