import asyncio
import datetime
import json
import sys
import threading
from contextlib import asynccontextmanager
from typing import Callable, Any, Dict, AsyncIterator, Type

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
from port_ocean.utils.misc import convert_time_to_minutes
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import init_signal_handler, signal_handler
from port_ocean.version import __integration_version__


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

    async def calculate_next_resync(self, now: datetime.datetime) -> float | None:
        if self.config.runtime != "Saas" and not self.config.scheduled_resync_interval:
            # There is no scheduled resync outside of Saas runtime or if not configured
            return None

        interval = self.config.scheduled_resync_interval
        next_resync = None
        if self.config.runtime == "Saas":
            integration = await self.port_client.get_current_integration()
            interval_str = (
                integration.get("spec", {})
                .get("appSpec", {})
                .get("scheduledResyncInterval")
            )
            interval = convert_time_to_minutes(interval_str)

        next_resync_date = now + datetime.timedelta(minutes=float(interval or 0))
        next_resync = next_resync_date.now(datetime.timezone.utc).timestamp()
        return next_resync

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

        @asynccontextmanager
        async def lifecycle(_: FastAPI) -> AsyncIterator[None]:
            try:
                init_signal_handler()
                now = datetime.datetime.now()
                calculation = asyncio.create_task(self.calculate_next_resync(now))
                await self.integration.start()
                await self._setup_scheduled_resync()
                next_resync = await calculation
                await self.port_client.update_resync_state(
                    {
                        "next_resync": next_resync,
                    }
                )
                yield None
            except Exception:
                logger.exception("Integration had a fatal error. Shutting down.")
                sys.exit("Server stopped")
            finally:
                signal_handler.exit()

        self.fast_api_app.router.lifespan_context = lifecycle
        await self.fast_api_app(scope, receive, send)
