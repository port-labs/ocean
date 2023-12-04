from typing import Any, Literal

from pydantic import BaseSettings, BaseModel, Extra, AnyHttpUrl, parse_obj_as, validator

from port_ocean.config.base import BaseOceanSettings
from port_ocean.core.event_listener import EventListenerSettingsType

LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class ApplicationSettings(BaseSettings):
    log_level: LogLevelType = "INFO"
    port: int = 8000

    class Config:
        env_prefix = "APPLICATION__"
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, *_, **__):  # type: ignore
            return env_settings, init_settings


class PortSettings(BaseModel, extra=Extra.allow):
    client_id: str
    client_secret: str
    base_url: AnyHttpUrl = parse_obj_as(AnyHttpUrl, "https://api.getport.io")


class IntegrationSettings(BaseModel, extra=Extra.allow):
    identifier: str
    type: str
    config: dict[str, Any]

    @validator("identifier", "type")
    def validate_lower(cls, v: str) -> str:
        return v.lower()


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    port: PortSettings
    event_listener: EventListenerSettingsType
    integration: IntegrationSettings
