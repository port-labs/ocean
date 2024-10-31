from loguru import logger
from starlette.requests import Request
from starlette.responses import Response

from port_ocean.exceptions.api import BaseAPIException, InternalServerException
from .context.event import event_context, EventType
from .context.ocean import ocean
from .utils.misc import get_time, generate_uuid
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)


class RequestHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = get_time(seconds_precision=False)
        request_id = generate_uuid()

        with logger.contextualize(request_id=request_id):
            log_level = (
                "DEBUG"
                if request.url.path == "/docs" or request.url.path == "/openapi.json"
                else "INFO"
            )
            logger.bind(url=str(request.url), method=request.method).log(
                log_level, f"Request to {request.url.path} started"
            )
            response = await self._handle_silently(request, call_next)

            end_time = get_time(seconds_precision=False)
            time_elapsed = round(end_time - start_time, 5)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(time_elapsed)
            logger.bind(
                time_elapsed=time_elapsed, response_status=response.status_code
            ).log(log_level, f"Request to {request.url.path} ended")

            return response

    async def _handle_silently(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response: Response
        try:
            if request.url.path.startswith("/integration"):
                async with event_context(
                    EventType.HTTP_REQUEST, trigger_type="request"
                ):
                    await ocean.integration.port_app_config_handler.get_port_app_config()
                    response = await call_next(request)
            else:
                response = await call_next(request)

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

        return response
