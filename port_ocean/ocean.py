import sys
from typing import Callable

from fastapi import FastAPI, APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.types import Scope, Receive, Send

from port_ocean.clients.port.client import PortClient
from port_ocean.config.integration import (
    IntegrationConfiguration,
)
from port_ocean.context.ocean import (
    PortOceanContext,
    ocean,
    initialize_port_ocean_context,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.middlewares import request_handler


class Ocean:
    def __init__(
        self,
        app: FastAPI | None = None,
        integration_class: Callable[[PortOceanContext], BaseIntegration] | None = None,
        integration_router: APIRouter | None = None,
        config_factory: Callable[..., BaseModel] | None = None,
    ):
        initialize_port_ocean_context(self)
        self.fast_api_app = app or FastAPI()
        self.fast_api_app.middleware("http")(request_handler)

        self.config = IntegrationConfiguration(base_path="./")
        if config_factory:
            self.config.integration.config = config_factory(
                **self.config.integration.config
            ).dict()
        self.integration_router = integration_router or APIRouter()

        self.port_client = PortClient(
            base_url=self.config.port.base_url,
            client_id=self.config.port.client_id,
            client_secret=self.config.port.client_secret,
            integration_identifier=self.config.integration.identifier,
            integration_type=self.config.integration.type,
        )
        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @self.fast_api_app.on_event("startup")
        async def startup() -> None:
            try:
                await self.integration.start()
            except Exception as e:
                logger.error(f"Failed to start integration with error: {e}")
                sys.exit("Server stopped")

        await self.fast_api_app(scope, receive, send)
