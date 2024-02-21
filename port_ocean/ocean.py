import asyncio
import sys
import threading
from typing import Callable, Any, Dict

from fastapi import FastAPI, APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.types import Scope, Receive, Send

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import (
    IntegrationConfiguration,
)
from port_ocean.context.ocean import (
    PortOceanContext,
    ocean,
    initialize_port_ocean_context,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.middlewares import request_handler
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import init_signal_handler
from port_ocean.version import __integration_version__


class Ocean:
    def __init__(
        self,
        app: FastAPI | None = None,
        integration_class: Callable[[PortOceanContext], BaseIntegration] | None = None,
        integration_router: APIRouter | None = None,
        config_factory: Callable[..., BaseModel] | None = None,
        config_override: Dict[str, Any] | None = None,
    ):
        initialize_port_ocean_context(self)
        self.fast_api_app = app or FastAPI()
        self.fast_api_app.middleware("http")(request_handler)

        self.config = IntegrationConfiguration(
            base_path="./", **(config_override or {})
        )

        if config_factory:
            raw_config = (
                self.config.integration.config
                if isinstance(self.config.integration.config, dict)
                else self.config.integration.config.dict()
            )
            self.config.integration.config = config_factory(**raw_config)
        # add the integration sensitive configuration to the sensitive patterns to mask out
        sensitive_log_filter.hide_sensitive_strings(
            *self.config.get_sensitive_fields_data()
        )
        self.integration_router = integration_router or APIRouter()

        self.port_client = PortClient(
            base_url=self.config.port.base_url,
            client_id=self.config.port.client_id,
            client_secret=self.config.port.client_secret,
            integration_identifier=self.config.integration.identifier,
            integration_type=self.config.integration.type,
            integration_version=__integration_version__,
        )
        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

    async def _setup_scheduled_resync(
        self,
    ) -> None:
        def execute_resync_all() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting a new scheduled resync")
            loop.run_until_complete(self.integration.sync_raw_all())
            loop.close()

        interval = self.config.scheduled_resync_interval
        if interval is not None:
            logger.info(
                f"Setting up scheduled resync, the integration will automatically perform a full resync every {interval} minutes)"
            )
            repeated_function = repeat_every(
                seconds=interval * 60,
                # Not running the resync immediately because the event listener should run resync on startup
                wait_first=True,
            )(lambda: threading.Thread(target=execute_resync_all).start())
            await repeated_function()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @self.fast_api_app.on_event("startup")
        async def startup() -> None:
            init_signal_handler()
            try:
                await self.integration.start()
                await self._setup_scheduled_resync()
            except Exception:
                logger.exception("Failed to start integration")
                sys.exit("Server stopped")

        await self.fast_api_app(scope, receive, send)
