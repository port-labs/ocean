import inspect
import json
from pathlib import Path
from time import time
from typing import Callable, Any, Type, Optional, TypedDict
from uuid import uuid4

import yaml
from pydantic import BaseModel, Extra

from port_ocean.core.handlers.port_app_config.models import PortAppConfig


def get_time(seconds_precision: bool = True) -> float:
    """Return current time as Unix/Epoch timestamp, in seconds.
    :param seconds_precision: if True, return with seconds precision as integer (default).
                              If False, return with milliseconds precision as floating point number of seconds.
    """
    return time() if not seconds_precision else int(time())


def generate_uuid() -> str:
    """Return a UUID4 as string"""
    return str(uuid4())


def get_function_location(func: Callable[..., Any]) -> str:
    file_path = inspect.getsourcefile(func)
    line_number = inspect.getsourcelines(func)[1]
    return f"{file_path}:{line_number}"


def get_spec_file(path: Path = Path(".")) -> dict[str, Any] | None:
    try:
        return yaml.safe_load((path / ".port/spec.yaml").read_text())
    except FileNotFoundError:
        return None


class Preset(TypedDict):
    blueprint: str
    data: list[dict[str, Any]]


class Defaults(BaseModel, extra=Extra.allow):
    blueprints: list[dict[str, Any]] = []
    actions: list[Preset] = []
    scorecards: list[Preset] = []
    port_app_config: Optional[BaseModel]


def get_port_defaults(
    port_app_config_class: Type[PortAppConfig], base_path: Path = Path(".")
) -> Defaults | None:
    defaults_dir = base_path / ".port/defaults"
    if not defaults_dir.exists():
        return None

    if not defaults_dir.is_dir():
        raise Exception(f"Defaults directory is not a directory: {defaults_dir}")

    default_jsons = {}
    for path in defaults_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            raise Exception(
                f"Defaults directory should contain only json files. Found: {path}"
            )
        default_jsons[path.stem] = json.loads(path.read_text())

    return Defaults(
        blueprints=default_jsons.get("blueprints", []),
        actions=default_jsons.get("actions", []),
        scorecards=default_jsons.get("scorecards", []),
        port_app_config=port_app_config_class(
            **default_jsons.get("port_app_config", {})
        ),
    )
