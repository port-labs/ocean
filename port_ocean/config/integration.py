from typing import Any, Literal

from pydantic import BaseModel, Field, BaseSettings

from port_ocean.config.base import BaseOceanSettings
from port_ocean.core.trigger_channel import TriggerChannelSettingsType


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
    trigger_channel: TriggerChannelSettingsType = Field(alias="triggerChannel")
    batch_work_size: int | None = Field(alias="batchWorkSize", default=None)
    integration: IntegrationSettings


LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class LoggerConfiguration(BaseModel):
    level: LogLevelType = "DEBUG"
    serialize: bool = False
