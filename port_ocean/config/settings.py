from typing import Any, Literal

from port_ocean.config.base import BaseOceanSettings, BaseOceanModel
from port_ocean.core.event_listener import EventListenerSettingsType
from port_ocean.core.models import Runtime
from port_ocean.utils.misc import get_integration_name, get_spec_file
from pydantic import Extra, AnyHttpUrl, parse_obj_as
from pydantic.class_validators import root_validator, validator
from pydantic.env_settings import InitSettingsSource, EnvSettingsSource, BaseSettings
from pydantic.fields import Field
from pydantic.main import BaseModel

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
    identifier: str
    type: str
    config: dict[str, Any] | BaseModel = Field(default_factory=dict)

    @root_validator(pre=True)
    def root_validator(cls, values: dict[str, Any]) -> dict[str, Any]:
        integ_type = values.get("type")

        if not integ_type:
            integ_type = get_integration_name()

        values["type"] = integ_type.lower() if integ_type else None
        values["identifier"] = values.get(
            "identifier", f"my-{integ_type}-integration".lower()
        )

        return values


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    allow_environment_variables_jq_access: bool = True
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    client_timeout: int = 30
    send_raw_data_examples: bool = True
    port: PortSettings
    event_listener: EventListenerSettingsType
    # If an identifier or type is not provided, it will be generated based on the integration name
    integration: IntegrationSettings = IntegrationSettings(type="", identifier="")
    runtime: Runtime = "OnPrem"

    @validator("runtime")
    def validate_runtime(cls, runtime: Literal["OnPrem", "Saas"]) -> Runtime:
        if runtime == "Saas":
            spec = get_spec_file()
            if spec is None:
                raise ValueError(
                    "Could not determine whether it's safe to run "
                    "the integration due to not found spec.yaml."
                )

            saas_config = spec.get("saas")
            if saas_config and not saas_config["enabled"]:
                raise ValueError("This integration can't be ran as Saas")

        return runtime
