import warnings
from typing import Any

from pydantic import BaseModel, Field
from pydantic import BaseSettings

from port_ocean.config.base import BaseOceanSettings
from port_ocean.core.trigger_channel.settings import (
    HttpTriggerChannelSettings,
    KafkaTriggerChannelSettings,
)

warnings.filterwarnings("ignore", category=FutureWarning)


class PortSettings(BaseSettings):
    client_id: str = Field(alias="clientId")
    client_secret: str = Field(alias="clientSecret")
    base_url: str = Field(alias="baseUrl")


class IntegrationSettings(BaseSettings):
    identifier: str
    type: str
    config: dict[str, Any]


class IntegrationConfiguration(BaseOceanSettings):
    port: PortSettings
    trigger_channel: KafkaTriggerChannelSettings | HttpTriggerChannelSettings = Field(
        alias="triggerChannel"
    )
    batch_work_size: int | None = Field(alias="batchWorkSize", default=None)
    integration: IntegrationSettings


class LoggerConfiguration(BaseModel):
    level: str = "DEBUG"
    serialize: bool = False
