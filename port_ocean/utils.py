import asyncio
import inspect
from asyncio import ensure_future
from functools import wraps
from importlib.util import module_from_spec, spec_from_file_location
from time import time
from traceback import format_exception
from types import ModuleType
from typing import Callable, Any, Coroutine
from uuid import uuid4

import httpx
import tomli
import yaml
from loguru import logger
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.helpers.retry import RetryTransport

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context() -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = httpx.AsyncClient(
            transport=RetryTransport(
                httpx.AsyncHTTPTransport(),
                logger=logger,
            )
        )
        _http_client.push(client)

    return client


"""
Utilize this client for all outbound integration requests to the third-party application. It functions as a wrapper 
around the httpx.AsyncClient, incorporating retry logic at the transport layer for handling retries on 5xx errors and
connection errors.

The client is instantiated lazily, only coming into existence upon its initial access. It should not be closed when in
use, as it operates as a singleton shared across all events in the thread. It also takes care of recreating the client
in scenarios such as the creation of a new event loop, such as when initiating a new thread.
"""
http_async_client: httpx.AsyncClient = LocalProxy(lambda: _get_http_client_context())  # type: ignore


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


def get_integration_version() -> str:
    try:
        with open("./pyproject.toml", "rb") as toml_file:
            pyproject_data = tomli.load(toml_file)
            return pyproject_data["tool"]["poetry"]["version"]
    except (FileNotFoundError, KeyError):
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


NoArgsNoReturnFuncT = Callable[[], None]
NoArgsNoReturnAsyncFuncT = Callable[[], Coroutine[Any, Any, None]]
NoArgsNoReturnDecorator = Callable[
    [NoArgsNoReturnFuncT | NoArgsNoReturnAsyncFuncT], NoArgsNoReturnAsyncFuncT
]


def repeat_every(
    seconds: float,
    wait_first: bool = False,
    raise_exceptions: bool = False,
    max_repetitions: int | None = None,
) -> NoArgsNoReturnDecorator:
    """
    This function returns a decorator that modifies a function so it is periodically re-executed after its first call.

    The function it decorates should accept no arguments and return nothing. If necessary, this can be accomplished
    by using `functools.partial` or otherwise wrapping the target function prior to decoration.

    Parameters
    ----------
    seconds: float
        The number of seconds to wait between repeated calls
    wait_first: bool (default False)
        If True, the function will wait for a single period before the first call
    raise_exceptions: bool (default False)
        If True, errors raised by the decorated function will be raised to the event loop's exception handler.
        Note that if an error is raised, the repeated execution will stop.
        Otherwise, exceptions are just logged and the execution continues to repeat.
        See https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_exception_handler for more info.
    max_repetitions: Optional[int] (default None)
        The maximum number of times to call the repeated function. If `None`, the function is repeated forever.
    """

    def decorator(
        func: NoArgsNoReturnAsyncFuncT | NoArgsNoReturnFuncT,
    ) -> NoArgsNoReturnAsyncFuncT:
        """
        Converts the decorated function into a repeated, periodically-called version of itself.
        """
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapped() -> None:
            repetitions = 0

            async def loop() -> None:
                nonlocal repetitions

                if wait_first:
                    await asyncio.sleep(seconds)
                while max_repetitions is None or repetitions < max_repetitions:
                    # count the repetition even if an exception is raised
                    repetitions += 1
                    try:
                        if is_coroutine:
                            await func()  # type: ignore
                        else:
                            await run_in_threadpool(func)
                    except Exception as exc:
                        formatted_exception = "".join(
                            format_exception(type(exc), exc, exc.__traceback__)
                        )
                        logger.error(formatted_exception)
                        if raise_exceptions:
                            raise exc
                    await asyncio.sleep(seconds)

            ensure_future(loop())

        return wrapped

    return decorator
