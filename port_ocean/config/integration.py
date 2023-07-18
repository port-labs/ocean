from typing import Any, Literal

from pydantic import Field, BaseSettings

from port_ocean.config.base import BaseOceanSettings
from port_ocean.core.event_listener import EventListenerSettingsType


class PortSettings(BaseSettings):
    client_id: str = Field(alias="clientId")
    client_secret: str = Field(alias="clientSecret")
    base_url: str = Field(alias="baseUrl", default="https://api.getport.io")


class IntegrationSettings(BaseSettings):
    identifier: str
    type: str
    config: dict[str, Any]


class IntegrationConfiguration(BaseOceanSettings):
    port: PortSettings
    event_listener: EventListenerSettingsType = Field(alias="eventListener")
    batch_work_size: int | None = Field(alias="batchWorkSize", default=None)
    initialize_port_resources: bool = Field(
        alias="initializePortResources", default=False
    )
    integration: IntegrationSettings


LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class ApplicationSettings(BaseSettings):
    log_level: LogLevelType = "DEBUG"
    port: int = 8000

    class Config:
        env_prefix = "APPLICATION_"
