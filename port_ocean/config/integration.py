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
    kafka_consumer_brokers: str = ""
    kafka_consumer_security_protocol: str = "SASL_SSL"
    kafka_consumer_authentication_mechanism: str = "SCRAM-SHA-512"
    kafka_security_enabled: bool = True


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
