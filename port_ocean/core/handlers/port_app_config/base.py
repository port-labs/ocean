from abc import abstractmethod
from typing import Type, Any

from loguru import logger
from pydantic import ValidationError

from port_ocean.context.event import event
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.utils.misc import get_time


class PortAppConfigCache:
    _port_app_config: PortAppConfig | None
    _retrieval_time: float

    def __init__(self, cache_ttl: int):
        self._port_app_config = None
        self._cache_ttl = cache_ttl

    @property
    def port_app_config(self) -> PortAppConfig:
        if self._port_app_config is None:
            raise ValueError("Port app config is not set")
        return self._port_app_config

    @port_app_config.setter
    def port_app_config(self, value: PortAppConfig) -> None:
        self._retrieval_time = get_time()
        self._port_app_config = value

    @property
    def is_cache_invalid(self) -> bool:
        return (
            not self._port_app_config
            or self._retrieval_time + self._cache_ttl < get_time()
        )


class BasePortAppConfig(BaseHandler):
    """Abstract base class for managing port application configurations.

    This class defines methods for obtaining and processing port application configurations.

    Attributes:
        context (Any): The context to be used during port application configuration.
        CONFIG_CLASS (Type[PortAppConfig]): The class used for defining port application configuration settings.
    """

    CONFIG_CLASS: Type[PortAppConfig] = PortAppConfig

    def __init__(self, context: PortOceanContext):
        super().__init__(context)
        self._app_config_cache = PortAppConfigCache(
            self.context.config.port.port_app_config_cache_ttl
        )

    @abstractmethod
    async def _get_port_app_config(self) -> dict[str, Any]:
        pass

    async def get_port_app_config(self, use_cache: bool = True) -> PortAppConfig:
        """
        Retrieve and parse the port application configuration.

        :param use_cache: Determines whether to use the cached port-app-config if it exists, or to fetch it regardless
        :return: The parsed port application configuration.
        """
        if not use_cache or self._app_config_cache.is_cache_invalid:
            raw_config = await self._get_port_app_config()
            try:
                self._app_config_cache.port_app_config = self.CONFIG_CLASS.parse_obj(
                    raw_config
                )
            except ValidationError as e:
                logger.error(f"Invalid port app config found: {str(e)}")
                logger.warning(f"Invalid port app config: {raw_config}")
                raise

        event.port_app_config = self._app_config_cache.port_app_config
        return self._app_config_cache.port_app_config
