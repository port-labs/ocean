import datetime
import inspect
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from time import time
from types import ModuleType
from typing import Callable, Any
from uuid import uuid4


import tomli
import yaml


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


def convert_str_to_datetime(time_str: str) -> datetime.datetime | None:
    """
    Convert a string representing time to a datetime object.
    :param time_str: a string representing time in the format "2021-09-01T12:00:00Z"
    """
    if time_str.endswith("Z"):
        aware_date = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    aware_date = datetime.datetime.fromisoformat(time_str)
    return datetime.datetime.fromtimestamp(aware_date.timestamp())


def convert_time_to_minutes(time_str: str) -> int:
    """
    Convert a string representing time to minutes.
    :param time_str: a string representing time in the format "1h" or "1m"
    """
    if time_str.endswith("h"):
        hours = int(time_str[:-1])
        return hours * 60
    elif time_str.endswith("m"):
        minutes = int(time_str[:-1])
        return minutes
    else:
        raise ValueError("Invalid format. Expected a string ending with 'h' or 'm'.")


def get_next_occurrence(
    interval_seconds: int,
    start_time: datetime.datetime,
    now: datetime.datetime | None = None,
) -> datetime.datetime:
    """
    Predict the next occurrence of an event based on interval, start time, and current time.

    :param interval_minutes: Interval between occurrences in minutes.
    :param start_time: Start time of the event as a datetime object.
    :param now: Current time as a datetime object.
    :return: The next occurrence time as a datetime object.
    """

    if now is None:
        now = datetime.datetime.now()
    # Calculate the total minutes elapsed since the start time
    elapsed_seconds = (now - start_time).total_seconds()

    # Calculate the number of intervals that have passed
    intervals_passed = int(elapsed_seconds // interval_seconds)

    # Calculate the next occurrence time
    next_occurrence = start_time + datetime.timedelta(
        seconds=(intervals_passed + 1) * interval_seconds
    )

    return next_occurrence
