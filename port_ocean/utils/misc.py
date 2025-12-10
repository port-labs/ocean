import inspect
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
import multiprocessing
from pathlib import Path
from time import time
from types import ModuleType
from typing import Any, Callable
from uuid import uuid4

import tomli
import yaml


class IntegrationStateStatus(Enum):
    Running = "running"
    Failed = "failed"
    Completed = "completed"
    Aborted = "aborted"


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


def get_pyproject_data() -> dict[str, Any] | None:
    try:
        with open("./pyproject.toml", "rb") as toml_file:
            pyproject_data = tomli.load(toml_file)
            return pyproject_data["tool"]["poetry"]
    except (FileNotFoundError, KeyError):
        return None


def get_integration_version() -> str:
    if data := get_pyproject_data():
        return data["version"]
    return ""


def get_integration_name() -> str:
    if data := get_pyproject_data():
        return data["name"]
    return ""


def get_spec_file(path: Path = Path(".")) -> dict[str, Any] | None:
    try:
        return yaml.safe_load((path / ".port/spec.yaml").read_text())
    except FileNotFoundError:
        return None


def load_module(file_path: str) -> ModuleType:
    spec = spec_from_file_location("module.name", file_path)
    if spec is None or spec.loader is None:
        raise Exception(f"Failed to load integration from path: {file_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def get_cgroup_cpu_limit() -> int:
    try:
        with open("/sys/fs/cgroup/cpu.max", "r") as f:
            content = f.read().strip().split()
            # content will be like ['200000', '100000'] (quota, period) or ['max', '100000']
            if content[0] == "max":
                return (
                    multiprocessing.cpu_count()
                )  # No limit imposed, return host count

            quota_us = int(content[0])
            period_us = int(content[1])
            # Calculate the number of full CPUs: quota / period
            limit = int(quota_us // period_us)
            return limit if limit > 0 else 1
    except FileNotFoundError:
        # Fallback for cgroups v1 or other issues, might need to implement v1 logic
        # or use a reliable environment variable as a safeguard
        return multiprocessing.cpu_count()
    except Exception as e:
        print(f"Error reading cgroup limit: {e}")
        return multiprocessing.cpu_count()
