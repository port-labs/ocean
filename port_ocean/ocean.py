import asyncio
import sys
from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass
from types import ModuleType
from typing import Type, Callable

import uvicorn
from fastapi import FastAPI, APIRouter
from loguru import logger
from pydantic import BaseModel
from starlette.types import Scope, Receive, Send

from port_ocean.clients.port.client import PortClient
from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.integration import IntegrationConfiguration, LogLevelType
from port_ocean.context.ocean import (
    PortOceanContext,
    ocean,
    initialize_port_ocean_context,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.logger_setup import setup_logger
from port_ocean.middlewares import request_handler
from port_ocean.port_defaults import initialize_defaults
from port_ocean.utils import get_spec_file


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
    spec.loader.exec_module(module)

    return module


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


def run(path: str = ".", log_level: LogLevelType = "DEBUG") -> None:
    setup_logger(log_level)
    sys.path.append(".")
    try:
        integration_path = f"{path}/integration.py" if path else "integration.py"
        module = _load_module(integration_path)
        integration_class = _get_base_integration_class_from_module(module)
    except Exception:
        integration_class = None

    spec = get_spec_file()
    config_factory = None
    if spec is not None:
        config_factory = default_config_factory(spec.get("configurations", []))
    default_app = Ocean(
        integration_class=integration_class, config_factory=config_factory
    )

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = _load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app", default_app
    )

    defaults_task = initialize_defaults(
        app.integration.AppConfigHandlerClass.CONFIG_CLASS, app.config
    )
    asyncio.new_event_loop().run_until_complete(defaults_task)

    uvicorn.run(app, host="0.0.0.0", port=8000)
