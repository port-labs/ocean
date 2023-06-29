from time import time
from typing import Callable, Awaitable
from uuid import uuid4

from fastapi import Request, Response
from loguru import logger
from .context.event import event_context
from .context.ocean import ocean


def get_time(seconds_precision: bool = True) -> float:
    """Return current time as Unix/Epoch timestamp, in seconds.
    :param seconds_precision: if True, return with seconds precision as integer (default).
                              If False, return with milliseconds precision as floating point number of seconds.
    """
    return time() if not seconds_precision else int(time())


def get_uuid() -> str:
    """Return a UUID4 as string"""
    return str(uuid4())


async def request_handler(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware used by FastAPI to process each request, featuring:

    - Contextualize request logs with a unique Request ID (UUID4) for each unique request.
    - Catch exceptions during the request handling. Translate custom API exceptions into responses,
      or treat (and log) unexpected exceptions.
    """
    start_time = get_time(seconds_precision=False)
    request_id = get_uuid()

    with logger.contextualize(request_id=request_id):
        logger.bind(url=str(request.url), method=request.method).info("Request started")
        response: Response
        print(request.url.path)
        if request.url.path.startswith("/integration"):
            async with event_context(""):
                await ocean.integration.port_app_config_handler.get_port_app_config()
                response = await call_next(request)
        else:
            response = await call_next(request)

        end_time = get_time(seconds_precision=False)
        time_elapsed = round(end_time - start_time, 5)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(time_elapsed)
        logger.bind(
            time_elapsed=time_elapsed, response_status=response.status_code
        ).info("Request ended")
        return response
