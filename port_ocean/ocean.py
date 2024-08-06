import asyncio
import datetime
import sys
import threading
from contextlib import asynccontextmanager
from typing import Callable, Any, Dict, AsyncIterator, Type

from fastapi import FastAPI, APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.types import Scope, Receive, Send

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
from port_ocean.utils.signal import init_signal_handler, signal_handler
from port_ocean.version import __integration_version__
from port_ocean.utils.misc import get_next_occurrence


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
        self.created_at = datetime.datetime.now()

        # TODO: remove this once we separate the state from the integration
        self.last_resync_start: datetime.datetime | None = None
        self.last_integration_updated_at: str = ""
        # self.next_time_prediction: float | None = None  # TODO: delete
        # self.last_scheduled_execution: datetime.datetime | None = None  # TODO: delete

    def get_last_updated_at(self) -> str | None:
        return self.last_integration_updated_at

    def set_last_updated_at(self, last_updated_at: str) -> None:
        self.last_integration_updated_at = last_updated_at

    def is_saas(self) -> bool:
        return self.config.runtime == Runtime.Saas

    def _calculate_next_scheduled_resync(
        self,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> float | None:
        if interval is None:
            return None
        return get_next_occurrence(
            interval * 60, custom_start_time or self.created_at
        ).timestamp()

    async def update_state_before_scheduled_sync(
        self,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> None:
        _interval = interval or self.config.scheduled_resync_interval

        self.last_resync_start = datetime.datetime.now()
        integration = await self.port_client.update_integration_state(
            {
                "status": "running",
                "last_resync_start": self.last_resync_start.timestamp(),
                "last_resync_end": None,
                "interval": _interval,
                "next_resync": self._calculate_next_scheduled_resync(
                    _interval, custom_start_time
                ),
            }
        )
        self.set_last_updated_at(integration["updatedAt"])

    async def update_state_after_scheduled_sync(
        self,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> None:
        _interval = interval or self.config.scheduled_resync_interval

        integration = await self.port_client.update_integration_state(
            {
                "status": "completed",
                "last_resync_start": (
                    self.last_resync_start.timestamp()
                    if self.last_resync_start
                    else None
                ),
                "last_resync_end": datetime.datetime.now().timestamp(),
                "interval": _interval,
                "next_resync": self._calculate_next_scheduled_resync(
                    _interval, custom_start_time
                ),
            }
        )
        self.set_last_updated_at(integration["updatedAt"])
        # self.next_time_prediction = self._calculate_next_scheduled_resync(
        #     _interval, custom_start_time
        # )  # TODO: delete

    async def _setup_scheduled_resync(
        self,
    ) -> None:
        async def execute_resync_all() -> None:
            # logger.info(
            #     f"prediction was: {str(datetime.datetime.fromtimestamp(self.next_time_prediction or 0))}"
            #     + f" now is: {str(datetime.datetime.now())}"
            #     + f" last time this function ran was: {str(self.last_scheduled_execution)}"
            #     + f" time from last execution: {str(datetime.datetime.now() - (self.last_scheduled_execution or datetime.datetime.now()))}"
            # )  # TODO: delete

            # self.last_scheduled_execution = datetime.datetime.now()  # TODO: delete
            await self.update_state_before_scheduled_sync()
            logger.info("Starting a new scheduled resync")
            await self.integration.sync_raw_all()
            await self.update_state_after_scheduled_sync()

        interval = self.config.scheduled_resync_interval
        if interval is not None:
            logger.info(
                f"Setting up scheduled resync, the integration will automatically perform a full resync every {interval} minutes)"
            )
            repeated_function = repeat_every(
                seconds=interval * 60,
                # Not running the resync immediately because the event listener should run resync on startup
                wait_first=True,
            )(
                lambda: threading.Thread(
                    target=asyncio.run(execute_resync_all())
                ).start()
            )
            await repeated_function()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @asynccontextmanager
        async def lifecycle(_: FastAPI) -> AsyncIterator[None]:
            try:
                init_signal_handler()
                await self.integration.start()
                await self._setup_scheduled_resync()
                yield None
            except Exception:
                logger.exception("Integration had a fatal error. Shutting down.")
                sys.exit("Server stopped")
            finally:
                signal_handler.exit()

        self.fast_api_app.router.lifespan_context = lifecycle
        await self.fast_api_app(scope, receive, send)
