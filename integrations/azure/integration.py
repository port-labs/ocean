from requests import Request, Response
from typing import Awaitable, Callable

import fastapi
from loguru import logger
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from azure_integration.overrides import AzurePortAppConfig


class AzureIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig


async def cloud_event_validation_middleware_handler(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Middleware used to handle cloud event validation requests
    Azure topic subscription expects a 200 response with specific headers
    https://github.com/cloudevents/spec/blob/v1.0/http-webhook.md#42-validation-response
    """
    if request.method == "OPTIONS" and request.url.path.startswith("/integration"):
        logger.info("Detected cloud event validation request")
        headers = {
            "WebHook-Allowed-Rate": "100",
            "WebHook-Allowed-Origin": "*",
        }
        response = fastapi.Response(status_code=200, headers=headers)
        return response

    return await call_next(request)
