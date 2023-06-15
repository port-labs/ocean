from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass
from types import ModuleType
from typing import Type

import uvicorn
from fastapi import FastAPI, APIRouter
from loguru import logger

from port_ocean.clients.port import PortClient
from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.context.integration import PortOceanContext
from port_ocean.core.integrations.base import BaseIntegration


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
        logger.error(
            f"Failed to load integration with error: {e}, "
            f"please validate the integration type exists"
        )
        raise e

    return module


def _include_target_channel_router(app: FastAPI, ocean: PortOceanContext) -> None:
    target_channel_router = APIRouter()

    @target_channel_router.post("/resync")
    async def resync() -> None:
        if ocean.integration is None:
            raise Exception("Integration not set")

        await ocean.integration.trigger_resync()

    app.include_router(target_channel_router)


def run(path: str) -> None:
    from port_ocean.context.integration import initialize_port_ocean_context, ocean

    config = IntegrationConfiguration(base_path=path)
    app = FastAPI()
    router = APIRouter()
    port_client = PortClient(
        base_url=config.port.base_url,
        client_id=config.port.client_id,
        client_secret=config.port.client_secret,
        user_agent=config.integration.identifier,
    )
    initialize_port_ocean_context(config, port_client, router)
    module = _load_module(f"{path}/integration.py")
    integration_class = _get_base_integration_class_from_module(module)

    integration = integration_class(ocean)
    ocean.integration = integration

    _load_module(f"{path}/main.py")

    app.include_router(router, prefix="/integration")
    if config.trigger_channel.type == "http":
        _include_target_channel_router(app, ocean)

    @app.on_event("startup")
    async def startup() -> None:
        await integration.trigger_start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
