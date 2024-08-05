import os
import re
from types import GenericAlias
from typing import Any

import yaml
from humps import decamelize
from pathlib import Path
from pydantic import BaseSettings
from pydantic.env_settings import EnvSettingsSource, InitSettingsSource
from pydantic.main import ModelMetaclass, BaseModel

PROVIDER_WRAPPER_PATTERN = r"{{ from (.*) }}"
PROVIDER_CONFIG_PATTERN = r"^[a-zA-Z0-9]+ .*$"


def read_yaml_config_settings_source(settings: "BaseOceanSettings") -> dict[str, Any]:
    yaml_file = getattr(settings.Config, "yaml_file", "")

    assert yaml_file, "Settings.yaml_file not properly configured"
    path = Path(
        getattr(
            settings,
            "_base_path",
        ),
        yaml_file,
    )

    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text("utf-8"))


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
    settings_model: BaseModel | ModelMetaclass,
    config: dict[str, Any],
    existing_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalizing the config yaml file to work with snake_case and getting only the data that is missing for the settings
    """
    for key, value in config.items():
        if isinstance(value, dict) and settings_model is not None:
            # If the value is of type ModelMetaClass then its a nested model, and we need to parse it
            # If the value is of type primitive dict then we need to decamelize the keys and not recurse into the values because its no longer part of the model
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
    settings_model: BaseModel | ModelMetaclass, config: dict[str, Any]
) -> dict[str, Any]:
    """
    Normalizing the config yaml file to work with snake_case and getting only the data that is missing for the settings
    """
    result = {}
    for key, value in config.items():
        decamelize_key = decamelize(key)
        if isinstance(value, dict) and settings_model is not None:
            # If the value is ModelMetaClass typed then its a nested model, and we need to parse it
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


def load_providers(
    settings: "BaseOceanSettings", existing_values: dict[str, Any]
) -> dict[str, Any]:
    data = read_yaml_config_settings_source(settings)
    snake_case_config = decamelize_config(settings, data)
    return parse_providers(settings, snake_case_config, existing_values)


class BaseOceanSettings(BaseSettings):
    _base_path: str = "./"

    def get_sensitive_fields_data(self) -> set[str]:
        return _get_sensitive_information(self)

    class Config:
        yaml_file = "./config.yaml"
        env_prefix = "OCEAN__"
        env_nested_delimiter = "__"
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
            return (
                init_settings,
                env_settings,
                lambda s: load_providers(s, {**env_settings(s), **init_settings(s)}),
            )


class BaseOceanModel(BaseModel):
    def get_sensitive_fields_data(self) -> set[str]:
        return _get_sensitive_information(self)


def _get_sensitive_information(
    model: BaseOceanModel | BaseSettings,
) -> set[str]:
    sensitive_fields = [
        field_name
        for field_name, field in model.__fields__.items()
        if field.field_info.extra.get("sensitive", False)
    ]
    sensitive_set = {str(getattr(model, field_name)) for field_name in sensitive_fields}

    recursive_sensitive_data = [
        getattr(model, field_name).get_sensitive_fields_data()
        for field_name, field in model.__fields__.items()
        if isinstance(getattr(model, field_name), BaseOceanModel)
    ]
    for sensitive_data in recursive_sensitive_data:
        sensitive_set.update(sensitive_data)

    return sensitive_set
