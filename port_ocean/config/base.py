import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from humps import decamelize
from pydantic import BaseSettings
from pydantic.env_settings import EnvSettingsSource

PROVIDER_WRAPPER_PATTERN = r"\{\{ from (.*) \}\}"
PROVIDER_CONFIG_PATTERN = r"^[a-zA-Z0-9]+ .*$"
DEFAULT_CONFIG_PATH = "./config.yaml"


def read_yaml_config_settings_source(config_path: str) -> str:
    parsed_url = urlparse(config_path)
    if parsed_url.scheme == "file" or not parsed_url.scheme:
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Could not open yaml settings file at: {path}")

        return path.read_text("utf-8")
    elif parsed_url.scheme in ["http", "https"]:
        config_response = httpx.get(config_path)
        config_response.raise_for_status()
        return config_response.text
    else:
        raise ValueError(f"Invalid config path: {config_path}")


def parse_config_provider(value: str) -> tuple[str, str]:
    match = re.match(PROVIDER_CONFIG_PATTERN, value)
    if not match:
        raise ValueError(
            f"Invalid pattern: {value}. Pattern should match: {PROVIDER_CONFIG_PATTERN}"
        )

    provider_type, provider_value = value.split(" ", 1)

    return provider_type, provider_value


def load_from_config_provider(provider_type: str, value: str) -> Any:
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


def load_providers(config_path: str) -> dict[str, Any]:
    yaml_content = read_yaml_config_settings_source(config_path)
    matches = re.finditer(PROVIDER_WRAPPER_PATTERN, yaml_content)
    for match in matches:
        provider_type, provider_value = parse_config_provider(match.group(1))
        data = load_from_config_provider(provider_type, provider_value)
        # Replace the provider wrapper with the actual value
        yaml_content = re.sub(re.escape(match.group()), data, yaml_content, count=1)

    return decamelize_object(yaml.safe_load(yaml_content))


class BaseOceanSettings(BaseSettings):
    config_path: str | None = DEFAULT_CONFIG_PATH

    class Config:
        @classmethod
        def customise_sources(cls, init_settings, env_settings: EnvSettingsSource, *_, **__):  # type: ignore
            return (
                env_settings,
                init_settings,
                lambda s: load_providers(
                    init_settings.init_kwargs["config_path"] or DEFAULT_CONFIG_PATH
                ),
            )
