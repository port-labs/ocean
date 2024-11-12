import asyncio
import sys
import threading
from contextlib import asynccontextmanager
from typing import Callable, Any, Dict, AsyncIterator, Type

from fastapi import FastAPI, APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.types import Scope, Receive, Send

from port_ocean.core.handlers.resync_state_updater import ResyncStateUpdater
from port_ocean.core.models import Runtime
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
from port_ocean.utils.signal import signal_handler
from port_ocean.version import __integration_version__
from port_ocean.utils.misc import IntegrationStateStatus


class Ocean:
    def __init__(
        self,
        app: FastAPI | None = None,
        integration_class: Callable[[PortOceanContext], BaseIntegration] | None = None,
        integration_router: APIRouter | None = None,
        config_factory: Type[BaseModel] | None = None,
        config_override: Dict[str, Any] | None = None,
    ):
        initialize_port_ocean_context(self)
        self.fast_api_app = app or FastAPI()
        self.fast_api_app.middleware("http")(request_handler)

        self.config = IntegrationConfiguration(
            # type: ignore
            _integration_config_model=config_factory,
            **(config_override or {}),
        )

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

        self.resync_state_updater = ResyncStateUpdater(
            self.port_client, self.config.scheduled_resync_interval
        )

        self.app_initialized = False

    def is_saas(self) -> bool:
        return self.config.runtime == Runtime.Saas

    async def _setup_scheduled_resync(
        self,
    ) -> None:
        async def execute_resync_all() -> None:
            await self.resync_state_updater.update_before_resync()
            logger.info("Starting a new scheduled resync")
            try:
                await self.integration.sync_raw_all()
                await self.resync_state_updater.update_after_resync()
            except asyncio.CancelledError:
                logger.warning(
                    "resync was cancelled by the scheduled resync, skipping state update"
                )
            except Exception as e:
                await self.resync_state_updater.update_after_resync(
                    IntegrationStateStatus.Failed
                )
                raise e

        interval = self.config.scheduled_resync_interval
        loop = asyncio.get_event_loop()
        if interval is not None:
            logger.info(
                f"Setting up scheduled resync, the integration will automatically perform a full resync every {interval} minutes)",
                scheduled_interval=interval,
            )
            repeated_function = repeat_every(
                seconds=interval * 60,
                # Not running the resync immediately because the event listener should run resync on startup
                wait_first=True,
            )(
                lambda: threading.Thread(
                    target=lambda: asyncio.run_coroutine_threadsafe(
                        execute_resync_all(), loop
                    )
                ).start()
            )
            await repeated_function()

    def initialize_app(self) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @asynccontextmanager
        async def lifecycle(_: FastAPI) -> AsyncIterator[None]:
            try:
                await self.integration.start()
                await self._setup_scheduled_resync()
                yield None
            except Exception:
                logger.exception("Integration had a fatal error. Shutting down.")
                logger.complete()
                sys.exit("Server stopped")
            finally:
                signal_handler.exit()

        self.fast_api_app.router.lifespan_context = lifecycle
        self.app_initialized = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.app_initialized:
            self.initialize_app()

        await self.fast_api_app(scope, receive, send)
