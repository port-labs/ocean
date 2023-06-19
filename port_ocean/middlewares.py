from fastapi import Request, Response

from .exceptions.api.base import BaseAPIException, InternalServerException
from .logger import logger
from .utils import get_time, get_uuid


async def request_handler(request: Request, call_next):
    """Middleware used by FastAPI to process each request, featuring:

    - Contextualize request logs with an unique Request ID (UUID4) for each unique request.
    - Catch exceptions during the request handling. Translate custom API exceptions into responses,
      or treat (and log) unexpected exceptions.
    """
    start_time = get_time(seconds_precision=False)
    request_id = get_uuid()

    with logger.contextualize(request_id=request_id):
        logger.bind(url=str(request.url), method=request.method).info("Request started")

        # noinspection PyBroadException
        try:
            response: Response = await call_next(request)

        except BaseAPIException as ex:
            response = ex.response()
            if response.status_code < 500:
                logger.bind(exception=str(ex)).info(
                    "Request did not succeed due to client-side error"
                )
            else:
                logger.opt(exception=True).warning(
                    "Request did not succeed due to server-side error"
                )

        except Exception:
            logger.opt(exception=True).error("Request failed due to unexpected error")
            response = InternalServerException().response()

        end_time = get_time(seconds_precision=False)
        time_elapsed = round(end_time - start_time, 5)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(time_elapsed)
        logger.bind(
            time_elapsed=time_elapsed, response_status=response.status_code
        ).info("Request ended")
        return response
