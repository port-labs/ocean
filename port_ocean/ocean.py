import asyncio
import sys
from contextlib import asynccontextmanager
import threading
from typing import Any, AsyncIterator, Callable, Dict, Type

from port_ocean.cache.base import CacheProvider
from port_ocean.cache.disk import DiskCacheProvider
from port_ocean.cache.memory import InMemoryCacheProvider
from port_ocean.core.models import ProcessExecutionMode
import port_ocean.helpers.metric.metric

from fastapi import FastAPI, APIRouter

from loguru import logger
from pydantic import BaseModel
from starlette.types import Receive, Scope, Send

from port_ocean.clients.port.client import PortClient
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
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import signal_handler
from port_ocean.version import __integration_version__
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)


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
        self.cache_provider: CacheProvider = self._get_caching_provider()
        self.process_execution_mode: ProcessExecutionMode = (
            self._get_process_execution_mode()
        )
        self.metrics = port_ocean.helpers.metric.metric.Metrics(
            metrics_settings=self.config.metrics,
            integration_configuration=self.config.integration,
            port_client=self.port_client,
            multiprocessing_enabled=self.process_execution_mode
            == ProcessExecutionMode.multi_process,
        )

        self.webhook_manager = LiveEventsProcessorManager(
            self.integration_router,
            signal_handler,
            max_event_processing_seconds=self.config.max_event_processing_seconds,
            max_wait_seconds_before_shutdown=self.config.max_wait_seconds_before_shutdown,
        )

        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

        self.resync_state_updater = ResyncStateUpdater(
            self.port_client, self.config.scheduled_resync_interval
        )
        self.app_initialized = False

    def _get_process_execution_mode(self) -> ProcessExecutionMode:
        if self.config.process_execution_mode:
            return self.config.process_execution_mode
        return ProcessExecutionMode.single_process

    def _get_caching_provider(self) -> CacheProvider:
        if self.config.caching_storage_mode:
            caching_type_to_provider = {
                DiskCacheProvider.STORAGE_TYPE: DiskCacheProvider,
                InMemoryCacheProvider.STORAGE_TYPE: InMemoryCacheProvider,
            }
            if self.config.caching_storage_mode in caching_type_to_provider:
                return caching_type_to_provider[self.config.caching_storage_mode]()

        if self.config.process_execution_mode == ProcessExecutionMode.multi_process:
            return DiskCacheProvider()
        return InMemoryCacheProvider()

    def is_saas(self) -> bool:
        return self.config.runtime.is_saas_runtime

    async def _setup_scheduled_resync(
        self,
    ) -> None:
        async def execute_resync_all() -> None:
            await self.resync_state_updater.update_before_resync()
            logger.info("Starting a new scheduled resync")
            try:
                successed = await self.integration.sync_raw_all()
                await self.resync_state_updater.update_after_resync(
                    IntegrationStateStatus.Completed
                    if successed
                    else IntegrationStateStatus.Failed
                )
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

    @property
    def base_url(self) -> str:
        integration_config = self.config.integration.config
        if isinstance(integration_config, BaseModel):
            integration_config = integration_config.dict()
        if integration_config.get("app_host"):
            logger.warning(
                "The OCEAN__INTEGRATION__CONFIG__APP_HOST field is deprecated. Please use the OCEAN__BASE_URL field instead."
            )
        return self.config.base_url or integration_config.get("app_host")

    def load_external_oauth_access_token(self) -> str | None:
        if self.config.oauth_access_token_file_path is not None:
            try:
                with open(self.config.oauth_access_token_file_path, "r") as f:
                    return f.read()
            except Exception:
                logger.debug(
                    "Failed to load external oauth access token from file",
                    file_path=self.config.oauth_access_token_file_path,
                )
        return None

    def initialize_app(self) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")
        self.fast_api_app.include_router(
            self.metrics.create_mertic_router(), prefix="/metrics"
        )

        @asynccontextmanager
        async def lifecycle(_: FastAPI) -> AsyncIterator[None]:
            try:
                await self.integration.start()
                if self.base_url:
                    await self.webhook_manager.start_processing_event_messages()
                else:
                    logger.warning("No base URL provided, skipping webhook processing")
                await self._setup_scheduled_resync()
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
