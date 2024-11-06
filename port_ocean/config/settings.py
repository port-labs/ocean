from typing import Any, Literal, Type, cast

from pydantic import Extra, AnyHttpUrl, parse_obj_as, parse_raw_as
from pydantic.class_validators import root_validator, validator
from pydantic.env_settings import InitSettingsSource, EnvSettingsSource, BaseSettings
from pydantic.fields import Field
from pydantic.main import BaseModel

from port_ocean.config.base import BaseOceanSettings, BaseOceanModel
from port_ocean.core.event_listener import EventListenerSettingsType
from port_ocean.core.models import Runtime
from port_ocean.utils.misc import get_integration_name, get_spec_file

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
    config: Any = Field(default_factory=dict)

    @root_validator(pre=True)
    def root_validator(cls, values: dict[str, Any]) -> dict[str, Any]:
        integ_type = values.get("type")

        if not integ_type:
            integ_type = get_integration_name()

        values["type"] = integ_type.lower() if integ_type else None
        if not values.get("identifier"):
            values["identifier"] = f"my-{integ_type}-integration".lower()

        return values


class IntegrationConfiguration(BaseOceanSettings, extra=Extra.allow):
    _integration_config_model: BaseModel | None = None

    allow_environment_variables_jq_access: bool = True
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    client_timeout: int = 60
    send_raw_data_examples: bool = True
    port: PortSettings
    event_listener: EventListenerSettingsType = Field(
        default=cast(EventListenerSettingsType, {"type": "POLLING"})
    )
    # If an identifier or type is not provided, it will be generated based on the integration name
    integration: IntegrationSettings = Field(
        default_factory=lambda: IntegrationSettings(type="", identifier="")
    )
    runtime: Runtime = Runtime.OnPrem

    @root_validator()
    def validate_integration_config(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not (config_model := values.get("_integration_config_model")):
            return values

        # Using the integration dynamic config model to parse the config
        def parse_config(model: Type[BaseModel], config: Any) -> BaseModel:
            # In some cases, the config is parsed as a string so we need to handle it
            # Example: when the config is loaded from the environment variables and there is an object inside the config
            if isinstance(config, str):
                return parse_raw_as(model, config)
            else:
                return parse_obj_as(model, config)

        integration_config = values["integration"]
        integration_config.config = parse_config(
            config_model, integration_config.config
        )

        return values

    @validator("runtime")
    def validate_runtime(cls, runtime: Runtime) -> Runtime:
        if runtime == Runtime.Saas:
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
