from __future__ import annotations

import inspect
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
import multiprocessing
from pathlib import Path
import sys
from time import time
from types import ModuleType
from typing import Any, Callable, Type, TYPE_CHECKING, TypeVar
from uuid import uuid4

import tomli
import yaml

if TYPE_CHECKING:
    from port_ocean.core.integrations.base import BaseIntegration


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
            return pyproject_data.get("project") or pyproject_data.get("tool", {}).get(
                "poetry"
            )
    except FileNotFoundError:
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


type GenericClass = TypeVar("GenericClass", bound=Any)


def get_subclass_class_from_module(
    module: ModuleType,
    base_class: Type[GenericClass],
) -> Type[GenericClass] | None:

    for name, obj in inspect.getmembers(module):
        if (
            inspect.isclass(obj)
            and type(obj) is type
            and issubclass(obj, base_class)
            and obj != base_class
        ):
            return obj

    return None


def get_integration_class(
    path: str,
) -> Type["BaseIntegration"] | None:
    from port_ocean.core.integrations.base import BaseIntegration

    sys.path.append(".")
    integration_path = f"{path}/integration.py" if path else "integration.py"
    module = load_module(integration_path)
    return get_subclass_class_from_module(module, BaseIntegration)


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


def run_async_in_new_event_loop(coro: Any) -> None:
    """Run an async coroutine in a new event loop, ensuring proper cleanup.

    This utility function creates a new event loop, runs the coroutine, and ensures
    the loop is properly closed even if an exception occurs. This prevents issues
    with unclosed event loops causing errors during interpreter shutdown (e.g.,
    "I/O operation on closed kqueue object" on macOS).

    Exceptions raised by the coroutine will propagate up to the caller after cleanup.

    Args:
        coro: A coroutine to execute (result of calling an async function)

    Raises:
        Any exception raised by the coroutine will be propagated.

    Example:
        ```python
        async def my_async_function():
            await some_async_operation()

        run_async_in_new_event_loop(my_async_function())
        ```
    """
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()
