from requests import Request, Response
from typing import Awaitable, Callable

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from loguru import logger

from azure_integration.overrides import AzurePortAppConfig


class AzureIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig


async def cloud_event_validation_middleware_handler(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Middleware used to handle cloud event validation requests
    https://github.com/cloudevents/spec/blob/v1.0/http-webhook.md#42-validation-response
    """
    response = await call_next(request)
    if request.method == "OPTIONS" and request.url.path.startswith("/integration"):
        logger.info("Detected cloud event validation request", request=request)
        response.headers["WebHook-Allowed-Rate"] = "1000"
        response.headers["WebHook-Allowed-Origin"] = "*"
    return response
