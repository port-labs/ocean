import inspect
from time import time
from typing import Callable, Any
from uuid import uuid4


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
