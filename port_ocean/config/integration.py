import warnings
from typing import Dict, Any

from pydantic import BaseModel, Field

from port_ocean.config.base import BaseYamlSettings

warnings.filterwarnings("ignore", category=FutureWarning)


class PortSettings(BaseModel):
    client_id: str = Field(alias="clientId")
    client_secret: str = Field(alias="clientSecret")
    base_url: str = Field(alias="baseUrl")


class TriggerChannelSettings(BaseModel):
    type: str
    brokers: str = ""
    security_protocol: str = "SASL_SSL"
    authentication_mechanism: str = "SCRAM-SHA-512"


class IntegrationSettings(BaseModel):
    identifier: str
    type: str
    config: Dict[str, Any]


class IntegrationConfiguration(BaseYamlSettings):
    port: PortSettings
    trigger_channel: TriggerChannelSettings = Field(alias="triggerChannel")
    integration: IntegrationSettings


class LoggerConfiguration(BaseModel):
    level: str = "DEBUG"
    serialize: bool = False
