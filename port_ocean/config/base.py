import os
import re
from pathlib import Path
from typing import Any

import yaml
from humps import decamelize
from pydantic import BaseSettings
from pydantic.env_settings import EnvSettingsSource, InitSettingsSource

PROVIDER_WRAPPER_PATTERN = r"\\{\\{ from (.*) \\}\\}"
PROVIDER_CONFIG_PATTERN = r"^[a-zA-Z0-9]+ .*$"


def read_yaml_config_settings_source(
    settings: "BaseOceanSettings", base_path: str
) -> str:
    yaml_file = getattr(settings.__config__, "yaml_file", "")

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


def decamelize_object(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {decamelize(k): decamelize_object(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decamelize_object(v) for v in obj]
    else:
        return obj


def parse_config(
    config: dict[str, Any], existing_data: dict[str, Any]
) -> dict[str, Any]:
    for key, value in config.items():
        decamelize_key = decamelize(key)
        if isinstance(value, dict):
            existing_data[decamelize_key] = parse_config(
                value, existing_data.get(decamelize_key, {})
            )
        elif isinstance(value, str):
            if provider_match := re.match(PROVIDER_WRAPPER_PATTERN, value):
                if decamelize_key not in existing_data:
                    try:
                        existing_data[decamelize_key] = load_from_config_provider(
                            provider_match.group(1)
                        )
                    except ValueError:
                        pass
            else:
                existing_data[decamelize_key] = value
        else:
            existing_data[decamelize_key] = value
    return existing_data


def load_providers(
    settings: "BaseOceanSettings", existing_values: dict[str, Any], base_path: str
) -> dict[str, Any]:
    yaml_content = read_yaml_config_settings_source(settings, base_path)
    data = yaml.safe_load(yaml_content)
    return parse_config(data, existing_values)


class BaseOceanSettings(BaseSettings):
    base_path: str

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
                env_settings,
                lambda s: load_providers(
                    s, env_settings(s), init_settings.init_kwargs["base_path"]
                ),
                init_settings,
            )
