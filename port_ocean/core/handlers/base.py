from abc import abstractmethod
from logging import Logger

from port_ocean.context.integration import PortOceanContext


class BaseHandler:
    @abstractmethod
    def __init__(self, context: PortOceanContext, logger: Logger):
        self.context = context
        self.logger = logger
