from typing import Literal, Any

from pydantic import AnyHttpUrl, Field, BaseSettings


class TriggerChannelSettings(BaseSettings):
    type: str

    def to_request(self) -> dict[str, Any]:
        return {"type": self.type}


class HttpTriggerChannelSettings(TriggerChannelSettings):
    type: Literal["WEBHOOK"]
    app_host: AnyHttpUrl = Field(alias="appHost")

    def to_request(self) -> dict[str, Any]:
        return {
            **super().to_request(),
            "url": self.app_host + "/resync",
        }


class KafkaTriggerChannelSettings(TriggerChannelSettings):
    type: Literal["KAFKA"]
    brokers: str = ""
    security_protocol: str = Field(alias="securityProtocol", default="SASL_SSL")
    authentication_mechanism: str = Field(
        alias="authenticationMechanism", default="SCRAM-SHA-512"
    )
    kafka_security_enabled: bool = Field(alias="kafkaSecurityEnabled", default=True)
    consumer_poll_timeout: int = Field(alias="consumerPollTimeout", default=1)
