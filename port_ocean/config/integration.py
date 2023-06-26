import warnings
from typing import Dict, Any

from pydantic import BaseModel, Field

from port_ocean.config.base import BaseYamlSettings
from pydantic import BaseSettings


warnings.filterwarnings("ignore", category=FutureWarning)


class PortSettings(BaseSettings):
    client_id: str = Field(alias="clientId")
    client_secret: str = Field(alias="clientSecret")
    base_url: str = Field(alias="baseUrl")

    class Config(BaseSettings.Config):
        env_prefix = "PORT__"


class TriggerChannelSettings(BaseSettings):
    type: str
    brokers: str = ""
    security_protocol: str = Field(alias="securityProtocol", default="SASL_SSL")
    authentication_mechanism: str = Field(
        alias="authenticationMechanism", default="SCRAM-SHA-512"
    )
    kafka_security_enabled: bool = Field(alias="kafkaSecurityEnabled", default=False)

    class Config(BaseSettings.Config):
        env_prefix = "TRIGGER__"


class IntegrationSettings(BaseSettings):
    identifier: str
    type: str
    config: Dict[str, Any]

    class Config(BaseSettings.Config):
        env_prefix = "INTEGRATION__"


class IntegrationConfiguration(BaseYamlSettings):
    port: PortSettings
    trigger_channel: TriggerChannelSettings = Field(alias="triggerChannel")
    batch_work_size: int | None = Field(alias="batchWorkSize", default=None)
    integration: IntegrationSettings


class LoggerConfiguration(BaseModel):
    level: str = "DEBUG"
    serialize: bool = False
