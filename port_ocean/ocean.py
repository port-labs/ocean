import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, Type

from fastapi import APIRouter, FastAPI
from loguru import logger
from pydantic import BaseModel
from starlette.types import Receive, Scope, Send

from port_ocean.clients.port.client import PortClient
from port_ocean.helpers.load_config import load_integration_config_from_file
from port_ocean.config.settings import (
    IntegrationConfiguration,
)
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.handlers.resync_state_updater import ResyncStateUpdater
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.middlewares import request_handler
from port_ocean.utils.misc import IntegrationStateStatus
from port_ocean.utils.repeat import schedule_repeated_task
from port_ocean.utils.signal import signal_handler
from port_ocean.version import __integration_version__
from port_ocean.core.handlers.webhook.processor_manager import WebhookProcessorManager


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

        self.webhook_manager = WebhookProcessorManager(
            self.integration_router, signal_handler
        )

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
        return self.config.runtime.is_saas_runtime

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
        if interval is not None:
            logger.info(
                f"Setting up scheduled resync, the integration will automatically perform a full resync every {interval} minutes)",
                scheduled_interval=interval,
            )
            await schedule_repeated_task(execute_resync_all, interval * 60)

    async def load_integration_config(self) -> None:
        integration_config = load_integration_config_from_file(
            self.config.integration.config
        )
        self.config.integration.config = integration_config

    def should_load_config(self) -> bool:
        return self.config.config_file_path is not None

    async def _setup_scheduled_config_loading(self) -> None:
        seconds = self.config.config_reload_interval
        await schedule_repeated_task(
            self.load_integration_config,
            seconds,
        )

    def initialize_app(self) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")

        @asynccontextmanager
        async def lifecycle(_: FastAPI) -> AsyncIterator[None]:
            try:
                await self.integration.start()
                await self.webhook_manager.start_processing_event_messages()
                await self._setup_scheduled_resync()
                if self.should_load_config():
                    await self._setup_scheduled_config_loading()
                yield None
            except Exception:
                logger.exception("Integration had a fatal error. Shutting down.")
                logger.complete()
                sys.exit("Server stopped")
            finally:
                await signal_handler.exit()

        self.fast_api_app.router.lifespan_context = lifecycle
        self.app_initialized = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.app_initialized:
            self.initialize_app()

        await self.fast_api_app(scope, receive, send)
