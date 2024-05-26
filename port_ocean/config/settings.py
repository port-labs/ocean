from typing import Any, Literal

from pydantic import Extra, AnyHttpUrl, parse_obj_as
from pydantic.class_validators import root_validator
from pydantic.env_settings import InitSettingsSource, EnvSettingsSource, BaseSettings
from pydantic.fields import Field
from pydantic.main import BaseModel

from port_ocean.config.base import BaseOceanSettings, BaseOceanModel
from port_ocean.core.event_listener import EventListenerSettingsType
from port_ocean.utils.misc import get_integration_name

LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]


class ApplicationSettings(BaseSettings):
    log_level: LogLevelType = "INFO"
    enable_http_logging: bool = True
    port: int = 8000

    class Config:
        env_prefix = "APPLICATION__"
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(  # type: ignore
            cls,
            init_settings: InitSettingsSource,
            env_settings: EnvSettingsSource,
            *_,
            **__,
        ):
            return env_settings, init_settings


class PortSettings(BaseOceanModel, extra=Extra.allow):
    client_id: str = Field(..., sensitive=True)
    client_secret: str = Field(..., sensitive=True)
    base_url: AnyHttpUrl = parse_obj_as(AnyHttpUrl, "https://api.getport.io")
    port_app_config_cache_ttl: int = 60


class IntegrationSettings(BaseOceanModel, extra=Extra.allow):
    identifier: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    config: dict[str, Any] | BaseModel

    @root_validator(pre=True)
    def a(cls, values: dict[str, Any]) -> dict[str, Any]:
        integ_type = values.get("type")

        if not integ_type:
            integ_type = get_integration_name()

        values["type"] = integ_type.lower() if integ_type else None
        values["identifier"] = values.get(
            "identifier", f"my-{integ_type}-integration".lower()
        )

        return values


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    client_timeout: int = 30
    send_raw_data_examples: bool = True
    port: PortSettings
    event_listener: EventListenerSettingsType
    integration: IntegrationSettings
