import sys
from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass
from types import ModuleType
from typing import Type, Callable

import uvicorn
from fastapi import FastAPI, APIRouter
from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.context.ocean import (
    PortOceanContext,
    ocean,
    initialize_port_ocean_context,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.middlewares import request_handler
from pydantic import BaseSettings
from starlette.types import Scope, Receive, Send


def _get_base_integration_class_from_module(
    module: ModuleType,
) -> Type[BaseIntegration]:
    for name, obj in getmembers(module):
        if (
            isclass(obj)
            and type(obj) == type
            and issubclass(obj, BaseIntegration)
            and obj != BaseIntegration
        ):
            return obj

    raise Exception(f"Failed to load integration from module: {module.__name__}")


def _load_module(file_path: str) -> ModuleType:
    spec = spec_from_file_location("module_name", file_path)
    if spec is None or spec.loader is None:
        raise Exception(f"Failed to load integration from path: {file_path}")

    module = module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise e

    return module


def _include_target_channel_router(app: FastAPI, _ocean: PortOceanContext) -> None:
    target_channel_router = APIRouter()

    @target_channel_router.post("/resync")
    async def resync() -> None:
        if _ocean.integration is None:
            raise Exception("Integration not set")

        await _ocean.integration.sync_all()

    app.include_router(target_channel_router)


class Ocean:
    def __init__(
        self,
        app: FastAPI | None = None,
        integration_class: Callable[[PortOceanContext], BaseIntegration] | None = None,
        integration_router: APIRouter | None = None,
        config_class: Type[BaseSettings] | None = None,
    ):
        initialize_port_ocean_context(self)
        self.fast_api_app = app or FastAPI()
        self.fast_api_app.middleware("http")(request_handler)

        self.config = IntegrationConfiguration(base_path="./")
        if config_class:
            self.config.integration.config = config_class(
                **self.config.integration.config
            ).dict()
        self.integration_router = integration_router or APIRouter()

        self.port_client = PortClient(
            base_url=self.config.port.base_url,
            client_id=self.config.port.client_id,
            client_secret=self.config.port.client_secret,
            user_agent_id=self.config.integration.identifier,
        )
        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.fast_api_app.include_router(self.integration_router, prefix="/integration")
        if self.config.trigger_channel.type == "http":
            _include_target_channel_router(self.fast_api_app, ocean)

        @self.fast_api_app.on_event("startup")
        async def startup() -> None:
            try:
                await self.integration.start()
            except Exception as e:
                logger.error(f"Failed to start integration with error: {e}")
                sys.exit("Server stopped")

        await self.fast_api_app(scope, receive, send)


def run(path: str) -> None:
    sys.path.append(".")
    try:
        integration_path = f"{path}/integration.py" if path else "integration.py"
        module = _load_module(integration_path)
        integration_class = _get_base_integration_class_from_module(module)
    except Exception:
        integration_class = None

    default_app = Ocean(integration_class=integration_class)

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = _load_module(main_path)
    app = {name: item for name, item in getmembers(app_module)}.get("app", default_app)

    uvicorn.run(app, host="0.0.0.0", port=8000)
