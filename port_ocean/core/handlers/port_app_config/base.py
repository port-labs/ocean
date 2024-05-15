from abc import abstractmethod
from datetime import timedelta
from typing import Type, Any

from loguru import logger
from pydantic import ValidationError

from port_ocean.context.event import event
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.utils.misc import get_time


class BasePortAppConfig(BaseHandler):
    """Abstract base class for managing port application configurations.

    This class defines methods for obtaining and processing port application configurations.

    Attributes:
        context (Any): The context to be used during port application configuration.
        CONFIG_CLASS (Type[PortAppConfig]): The class used for defining port application configuration settings.
    """

    CONFIG_CLASS: Type[PortAppConfig] = PortAppConfig
    STALE_TIMEOUT: timedelta = timedelta(minutes=1)
    app_config_cache: PortAppConfig | None = None
    retrieval_time: float

    @abstractmethod
    async def _get_port_app_config(self) -> dict[str, Any]:
        pass

    async def get_port_app_config(self) -> PortAppConfig:
        """Retrieve and parse the port application configuration.

        Returns:
            PortAppConfig: The parsed port application configuration.
        """
        if (
            not self.app_config_cache
            or self.retrieval_time + self.STALE_TIMEOUT.total_seconds() < get_time()
        ):
            raw_config = await self._get_port_app_config()
            try:
                self.app_config_cache = self.CONFIG_CLASS.parse_obj(raw_config)
                self.retrieval_time = get_time()
            except ValidationError:
                logger.error(
                    "Invalid port app config found. Please check that the integration has been configured correctly."
                )
                raise

        event.port_app_config = self.app_config_cache
        return self.app_config_cache
