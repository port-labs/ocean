import os
import re
from pathlib import Path
from types import GenericAlias
from typing import Any

import yaml
from humps import decamelize
from pydantic.fields import FieldInfo
from pydantic.main import BaseModel
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import (
    InitSettingsSource,
    EnvSettingsSource,
    DotEnvSettingsSource,
    SecretsSettingsSource,
)

PROVIDER_WRAPPER_PATTERN = r"{{ from (.*) }}"
PROVIDER_CONFIG_PATTERN = r"^[a-zA-Z0-9]+ .*$"


def read_yaml_config_settings_source(
    settings: type[BaseSettings], base_path: str
) -> str:
    yaml_file = getattr(settings, "yaml_file", "")

    assert yaml_file, "Settings.yaml_file not properly configured"
    path = Path(base_path, yaml_file)

    if not path.exists():
        raise FileNotFoundError(f"Could not open yaml settings file at: {path}")

    return path.read_text("utf-8")


def parse_config_provider(value: str) -> tuple[str, str]:
    match = re.match(PROVIDER_CONFIG_PATTERN, value)
    if not match:
        raise ValueError(
            f"Invalid pattern: {value}. Pattern should match: {PROVIDER_CONFIG_PATTERN}"
        )

    provider_type, provider_value = value.split(" ", 1)

    return provider_type, provider_value


def load_from_config_provider(config_provider: str) -> Any:
    provider_type, value = parse_config_provider(config_provider)
    if provider_type == "env":
        result = os.environ.get(value)
        if result is None:
            raise ValueError(f"Environment variable not found: {value}")
        return result
    else:
        raise ValueError(f"Invalid provider type: {provider_type}")


def parse_providers(
    settings_model: type[BaseModel],
    config: dict[str, Any],
    existing_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalizing the config yaml file to work with snake_case and getting only the data that is missing for the settings
    """
    for key, value in config.items():
        if isinstance(value, dict) and settings_model is not None:
            # If the value is of type BaseModel then its nested model, and we need to parse it
            # If the value is of type primitive dict then we need to decamelize the keys and not recurse into the values because its no longer part of the model
            _type = settings_model.__annotations__[key]
            _type = settings_model.__annotations__[key]
            is_primitive_dict_type = _type is dict or (
                isinstance(_type, GenericAlias) and _type.__origin__ is dict
            )

            if is_primitive_dict_type:
                _type = None
            existing_data[key] = parse_providers(
                _type, value, existing_data.get(key, {})
            )

        elif isinstance(value, str):
            # If the value is a provider, we try to load it from the provider
            if provider_match := re.match(PROVIDER_WRAPPER_PATTERN, value):
                # If the there is already value for that field, we ignore it
                # If the provider failed to load, we ignore it
                if key not in existing_data:
                    try:
                        existing_data[key] = load_from_config_provider(
                            provider_match.group(1)
                        )
                    except ValueError:
                        pass
            else:
                existing_data[key] = value
        else:
            existing_data[key] = value
    return existing_data


def decamelize_config(
    settings_model: type[BaseModel], config: dict[str, Any]
) -> dict[str, Any]:
    """
    Normalizing the config yaml file to work with snake_case and getting only the data that is missing for the settings
    """
    result = {}
    for key, value in config.items():
        decamelize_key = decamelize(key)
        if isinstance(value, dict) and settings_model is not None:
            # If the value is BaseModel typed then its nested model, and we need to parse it
            # If the value is a primitive dict then we need to decamelize the keys and not recurse into the values because its no longer part of the model
            _type = settings_model.__annotations__[decamelize_key]
            is_primitive_dict_type = _type is dict or (
                isinstance(_type, GenericAlias) and _type.__origin__ is dict
            )

            if is_primitive_dict_type:
                _type = None

            result[decamelize_key] = decamelize_config(_type, value)
        else:
            result[decamelize_key] = value
    return result


class MyCustomSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        env_settings: EnvSettingsSource,
        base_path: str,
    ):
        super().__init__(settings_cls)
        self.settings_cls = settings_cls
        self.config = settings_cls.model_config
        self.base_path = base_path
        self.env_settings = env_settings

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        # Nothing to do here. Only implement the return statement to make mypy happy
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        current_settings_value = self.env_settings()
        yaml_content = read_yaml_config_settings_source(
            self.settings_cls, self.base_path
        )
        data = yaml.safe_load(yaml_content)
        snake_case_config = decamelize_config(self.settings_cls, data)

        return parse_providers(
            self.settings_cls, snake_case_config, current_settings_value
        )


class BaseOceanSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCEAN__",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    yaml_file: Path = Path("./config.yaml")
    base_path: str

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,  # type: ignore
        env_settings: EnvSettingsSource,  # type: ignore
        dotenv_settings: DotEnvSettingsSource,  # type: ignore
        file_secret_settings: SecretsSettingsSource,  # type: ignore
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            MyCustomSource(
                settings_cls, env_settings, init_settings.init_kwargs["base_path"]
            ),
        )
