import re
from pathlib import Path
from typing import Dict, Any

import yaml
from pydantic import BaseSettings


def replace_secrets(secrets_dir: Path, data: str) -> str:
    """
    Replace "<file:xxxx>" secrets in given data
    """
    pattern = re.compile(r"\<file\:([^>]*)\>")

    for match in pattern.findall(data):
        relpath = Path(match)
        path = secrets_dir / relpath

        if not path.exists():
            raise FileNotFoundError(
                f"Secret file referenced in yaml file not found: {path}"
            )

        data = data.replace(f"<file:{match}>", path.read_text("utf-8"))
    return data


def yaml_config_settings_source(
    settings: "BaseYamlSettings", base_path: str
) -> Dict[str, Any]:
    """Loads settings from a YAML file at `Config.yaml_file`

    "<file:xxxx>" patterns are replaced with the contents of file xxxx. The root path
    were to find the files is configured with `secrets_dir`.
    """
    yaml_file = getattr(settings.__config__, "yaml_file", "")
    secrets_dir = settings.__config__.secrets_dir

    assert yaml_file, "Settings.yaml_file not properly configured"
    assert secrets_dir, "Settings.secrets_dir not properly configured"

    path = Path(base_path) / yaml_file
    secrets_path = Path(base_path) / secrets_dir

    if not path.exists():
        raise FileNotFoundError(f"Could not open yaml settings file at: {path}")

    return yaml.safe_load(replace_secrets(secrets_path, path.read_text("utf-8")))


class BaseYamlSettings(BaseSettings):
    base_path: str

    class Config:
        secrets_dir = "./secrets.yml"
        yaml_file = "./config.yaml"

        @classmethod
        def customise_sources(cls, init_settings, *_, **__):  # type: ignore
            return (
                init_settings,
                lambda s: yaml_config_settings_source(
                    s, init_settings.init_kwargs["base_path"]
                ),
            )
