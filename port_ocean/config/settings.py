from typing import Any, Literal

from pydantic import Extra, AnyHttpUrl, parse_obj_as, validator
from pydantic.fields import Field
from pydantic.main import BaseModel

from port_ocean.config.base import BaseOceanSettings, BaseOceanModel
from port_ocean.core.event_listener import EventListenerSettingsType

LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class ApplicationSettings(BaseOceanModel):
    log_level: LogLevelType = "INFO"
    enable_http_logging: bool = True
    port: int = 8000

    class Config:
        env_prefix = "APPLICATION__"
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, *_, **__):  # type: ignore
            return env_settings, init_settings


class PortSettings(BaseOceanModel, extra=Extra.allow):
    client_id: str = Field(..., sensitive=True)
    client_secret: str = Field(..., sensitive=True)
    base_url: AnyHttpUrl = parse_obj_as(AnyHttpUrl, "https://api.getport.io")


class IntegrationSettings(BaseOceanModel, extra=Extra.allow):
    identifier: str
    type: str
    config: dict[str, Any] | BaseModel

    @validator("identifier", "type")
    def validate_lower(cls, v: str) -> str:
        return v.lower()


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    client_timeout: int = 30
    port: PortSettings
    event_listener: EventListenerSettingsType
    integration: IntegrationSettings
