from abc import abstractmethod
from typing import Type, Any

from loguru import logger
from pydantic import ValidationError

from port_ocean.context.event import event
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class BasePortAppConfig(BaseHandler):
    """Abstract base class for managing port application configurations.

    This class defines methods for obtaining and processing port application configurations.

    Attributes:
        context (Any): The context to be used during port application configuration.
        CONFIG_CLASS (Type[PortAppConfig]): The class used for defining port application configuration settings.
    """

    CONFIG_CLASS: Type[PortAppConfig] = PortAppConfig

    @abstractmethod
    async def _get_port_app_config(self) -> dict[str, Any]:
        pass

    async def get_port_app_config(self) -> PortAppConfig:
        """Retrieve and parse the port application configuration.

        Returns:
            PortAppConfig: The parsed port application configuration.
        """
        raw_config = await self._get_port_app_config()
        try:
            config = self.CONFIG_CLASS.parse_obj(raw_config)
        except ValidationError:
            logger.error(
                "Invalid port app config found. Please check that the integration has been configured correctly."
            )
            raise

        event.port_app_config = config
        return config
