from typing import Any, Literal

from pydantic import BaseSettings, BaseModel, Extra, AnyHttpUrl, parse_obj_as

from port_ocean.config.base import BaseOceanSettings
from port_ocean.core.event_listener import EventListenerSettingsType


class PortSettings(BaseModel, extra=Extra.allow):
    client_id: str
    client_secret: str
    base_url: AnyHttpUrl = parse_obj_as(AnyHttpUrl, "https://api.getport.io")


class IntegrationSettings(BaseModel, extra=Extra.allow):
    identifier: str
    type: str
    config: dict[str, Any]


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    port: PortSettings
    event_listener: EventListenerSettingsType
    batch_work_size: int = 20
    initialize_port_resources: bool = False
    integration: IntegrationSettings

    class Config:
        env_prefix = "OCEAN__"
        env_nested_delimiter = "__"


LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class ApplicationSettings(BaseSettings):
    log_level: LogLevelType = "DEBUG"
    port: int = 8000

    class Config:
        env_prefix = "APPLICATION__"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, *_, **__):  # type: ignore
            return env_settings, init_settings
